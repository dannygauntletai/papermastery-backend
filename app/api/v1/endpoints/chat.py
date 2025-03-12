from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.api.v1.models import ChatRequest, ChatResponse
from app.core.logger import get_logger
from app.database.supabase_client import get_paper_by_id, insert_message, get_conversation, create_conversation
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
    2. Generate a response based on those chunks
    3. Return the response along with the source chunks
    
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
    conversation_id = str(paper_id)
    conversation = await get_conversation(conversation_id)
    if not conversation:
        try:
            # Create a conversation using the paper ID as the conversation ID
            await create_conversation({
                "id": conversation_id,
                "user_id": user_id
            })
            logger.info(f"Created conversation for paper with ID: {paper_id}")
        except Exception as e:
            logger.warning(f"Could not create conversation for paper: {str(e)}")
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
        logger.info(f"Saved user message for paper {paper_id}")
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
                logger.info(f"Saved bot message for paper {paper_id}")
            except Exception as e:
                logger.error(f"Error saving bot message: {str(e)}")
                # Continue even if message saving fails
            
            return ChatResponse(
                response=default_response,
                query=chat_request.query,
                sources=[],
                paper_id=paper_id
            )
            
        # Generate response based on chunks
        response_func = mock_generate_response if APP_ENV == "testing" else generate_response
        
        response_data = await response_func(
            query=chat_request.query,
            context_chunks=relevant_chunks,
            paper_title=paper.get("title", "")
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
            logger.info(f"Saved bot message for paper {paper_id}")
        except Exception as e:
            logger.error(f"Error saving bot message: {str(e)}")
            # Continue even if message saving fails
        
        # Construct the chat response
        return ChatResponse(
            response=response_data["response"],
            query=chat_request.query,
            sources=[
                {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "text": chunk.get("text", ""),
                    "metadata": chunk.get("metadata", {})
                }
                for chunk in relevant_chunks
            ],
            paper_id=paper_id
        )
        
    except Exception as e:
        logger.error(f"Error generating chat response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating chat response: {str(e)}"
        ) 