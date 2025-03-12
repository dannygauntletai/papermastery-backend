from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.api.v1.models import ChatRequest, ChatResponse, MessageResponse
from app.core.logger import get_logger
from app.database.supabase_client import get_paper_by_id, insert_message, get_conversation, create_conversation, get_conversation_messages
from app.services.pinecone_service import search_similar_chunks
from app.services.llm_service import generate_response, mock_generate_response
from app.dependencies import validate_environment, rate_limit, get_current_user
from app.core.config import APP_ENV

logger = get_logger(__name__)

router = APIRouter(
    prefix="/papers",
    tags=["chat"],
    dependencies=[Depends(validate_environment)]
)

@router.post("/{paper_id}/chat", response_model=ChatResponse)
async def chat_with_paper(
    paper_id: UUID,
    chat_request: ChatRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    rate_limited: bool = Depends(rate_limit),
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    Chat with a paper by asking questions about its content.
    
    The system will:
    1. Search for relevant chunks in the paper
    2. Generate a response based on those chunks or the full PDF
    3. Return the response along with the source quotes
    
    Args:
        paper_id: The UUID of the paper
        chat_request: The chat request containing the query
        request: The FastAPI request object
        user_id: The ID of the authenticated user
        rate_limited: Rate limiting dependency
        # args: Optional arguments (system use only)
        # kwargs: Optional keyword arguments (system use only)
        
    Returns:
        A response to the query along with sources
        
    Raises:
        HTTPException: If paper not found or other errors occur
    """
    logger.info(f"Chat request for paper {paper_id}: {chat_request.query[:50]}...")
    
    # Get the paper
    paper = await get_paper_by_id(paper_id)
    if not paper:
        logger.error(f"Paper not found: {paper_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found"
        )
    
    # Check if the paper has been processed (has embeddings)
    if not paper.get("embedding_id"):
        logger.error(f"Paper {paper_id} has not been fully processed")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This paper has not been fully processed yet. Please try again later."
        )
    
    # Ensure a conversation exists for this paper
    conversation_id = chat_request.conversation_id if chat_request.conversation_id else str(paper_id)
    conversation = await get_conversation(conversation_id)
    if not conversation:
        try:
            # Create a conversation using the provided ID or paper ID as fallback
            await create_conversation({
                "id": conversation_id,
                "user_id": user_id,
                "paper_id": str(paper_id)  # Ensure paper_id is set correctly
            })
            logger.info(f"Created conversation with ID: {conversation_id} for paper with ID: {paper_id}")
        except Exception as e:
            logger.warning(f"Could not create conversation: {str(e)}")
            # Continue even if conversation creation fails
    
    # Save the user message to the database
    try:
        user_message_data = {
            "user_id": user_id,
            "paper_id": str(paper_id),
            "conversation_id": conversation_id,
            "text": chat_request.query,
            "sender": "user"
        }
        await insert_message(user_message_data)
        logger.info(f"Saved user message for conversation {conversation_id}")
    except Exception as e:
        logger.error(f"Error saving user message: {str(e)}")
        # Continue even if message saving fails
    
    # Get relevant chunks from Pinecone
    try:
        relevant_chunks = await search_similar_chunks(
            query=chat_request.query,
            paper_id=paper_id,
            top_k=5  # Get top 5 most relevant chunks
        )
        
        if not relevant_chunks:
            logger.warning(f"No relevant chunks found for query: {chat_request.query[:50]}...")
            
            # Return a default response
            default_response = "I couldn't find specific information in this paper to answer your question. " \
                              "Could you try asking something more specific about the paper's content?"
            
            # Save the bot message to the database
            try:
                bot_message_data = {
                    "user_id": user_id,
                    "paper_id": str(paper_id),
                    "conversation_id": conversation_id,
                    "text": default_response,
                    "sender": "bot"
                }
                await insert_message(bot_message_data)
                logger.info(f"Saved bot message for conversation {conversation_id}")
            except Exception as e:
                logger.error(f"Error saving bot message: {str(e)}")
                # Continue even if message saving fails
            
            return ChatResponse(
                response=default_response,
                query=chat_request.query,
                sources=[],
                paper_id=paper_id
            )
            
        # Generate response based on chunks and/or PDF
        response_func = mock_generate_response if APP_ENV == "testing" else generate_response
        
        response_data = await response_func(
            query=chat_request.query,
            context_chunks=relevant_chunks,
            paper_title=paper.get("title", ""),
            paper_id=paper_id  # Pass paper_id to retrieve PDF
        )
        
        # Save the bot message to the database
        try:
            bot_message_data = {
                "user_id": user_id,
                "paper_id": str(paper_id),
                "conversation_id": conversation_id,
                "text": response_data["response"],
                "sender": "bot"
            }
            await insert_message(bot_message_data)
            logger.info(f"Saved bot message for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Error saving bot message: {str(e)}")
            # Continue even if message saving fails
        
        # Construct the chat response
        return ChatResponse(
            response=response_data["response"],
            query=chat_request.query,
            sources=response_data["sources"],  # Use the sources from the response
            paper_id=paper_id
        )
        
    except Exception as e:
        logger.error(f"Error generating chat response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating chat response: {str(e)}"
        )

@router.get("/{paper_id}/messages", response_model=List[MessageResponse])
async def get_paper_messages(
    paper_id: UUID,
    user_id: str = Depends(get_current_user),
    conversation_id: Optional[str] = Query(None, description="Optional conversation ID to filter messages")
):
    """
    Retrieve messages for a paper's conversations.
    
    Args:
        paper_id: The UUID of the paper
        user_id: The ID of the authenticated user
        conversation_id: Optional conversation ID to filter messages for a specific conversation
        
    Returns:
        A list of messages for the paper's conversations
        
    Raises:
        HTTPException: If paper not found or other errors occur
    """
    logger.info(f"Fetching messages for paper {paper_id}")
    
    # Get the paper
    paper = await get_paper_by_id(paper_id)
    if not paper:
        logger.error(f"Paper not found: {paper_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found"
        )
    
    try:
        # If conversation_id is provided, get messages for that specific conversation
        if conversation_id:
            messages = await get_conversation_messages(conversation_id)
            logger.info(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
        else:
            # For backward compatibility, use paper_id as conversation_id if no specific conversation_id is provided
            messages = await get_conversation_messages(str(paper_id))
            logger.info(f"Retrieved {len(messages)} messages using paper_id as conversation_id")
        
        # Convert to response model format
        return [
            MessageResponse(
                id=message.get("id"),
                text=message.get("text"),
                sender=message.get("sender"),
                created_at=message.get("created_at"),
                paper_id=message.get("paper_id"),
                conversation_id=message.get("conversation_id")
            )
            for message in messages
        ]
    except Exception as e:
        logger.error(f"Error retrieving messages for paper {paper_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving messages: {str(e)}"
        ) 