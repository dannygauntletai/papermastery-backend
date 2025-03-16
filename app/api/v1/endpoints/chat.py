from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.api.v1.models import ChatRequest, ChatResponse, MessageResponse, MessageSource
from app.core.logger import get_logger
from app.database.supabase_client import get_paper_by_id, insert_message, get_conversation, create_conversation, get_conversation_messages, get_paper_full_text
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
):
    """
    Chat with a paper by asking questions about its content.
    
    The system will:
    1. Retrieve the full text of the paper
    2. Generate a response based on the full text
    3. Return the response along with the source quotes
    
    Args:
        paper_id: The UUID of the paper
        chat_request: The chat request containing the query
        request: The FastAPI request object
        user_id: The ID of the authenticated user
        rate_limited: Rate limiting dependency
        
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
    
    # Check if the paper has been processed (has full text)
    full_text = await get_paper_full_text(paper_id)
    if not full_text or len(full_text) < 100:  # Minimal text check
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
    
    # Generate response based on full text
    try:
        response_func = mock_generate_response if APP_ENV == "testing" else generate_response
        
        # Create a context chunk from the full text
        context_chunks = [{
            "text": full_text[:8000],  # Use first 8000 chars to avoid token limits
            "metadata": {
                "paper_id": str(paper_id),
                "page_number": 1
            }
        }]
        
        response_data = await response_func(
            query=chat_request.query,
            context_chunks=context_chunks,
            paper_title=paper.get("title", ""),
            paper_id=paper_id
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
        
        # Extract sources from the response_data and convert to the new MessageSource format
        message_sources = []
        for source in response_data["sources"]:
            # Convert from the old format to the new MessageSource format
            message_source = MessageSource(
                text=source.get("text", ""),
                page=source.get("metadata", {}).get("page_number"),
                position=source.get("metadata", {})
            )
            message_sources.append(message_source)
        
        # Construct the chat response
        return ChatResponse(
            response=response_data["response"],
            conversation_id=conversation_id,
            sources=message_sources
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
                user_id=message.get("user_id", user_id),  # Use the current user_id as fallback
                paper_id=message.get("paper_id"),
                conversation_id=message.get("conversation_id"),
                query=message.get("text") if message.get("sender") == "user" else "",
                response=message.get("text") if message.get("sender") == "bot" else "",
                sources=None,  # No sources available in the existing message format
                timestamp=message.get("created_at")
            )
            for message in messages
        ]
    except Exception as e:
        logger.error(f"Error retrieving messages for paper {paper_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving messages: {str(e)}"
        ) 