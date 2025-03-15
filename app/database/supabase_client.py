from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from app.core.logger import get_logger
from app.core.exceptions import SupabaseError
from uuid import UUID
from typing import Dict, Any, Optional, List
from app.api.v1.models import SourceType

logger = get_logger(__name__)

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    raise SupabaseError(f"Failed to initialize Supabase client: {str(e)}")


async def get_paper_by_id(paper_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Retrieve a paper from the Supabase database by its ID.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        The paper data as a dictionary, or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the paper
    """
    try:
        response = supabase.table("papers").select("*").eq("id", str(paper_id)).execute()
        
        if len(response.data) == 0:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving paper with ID {paper_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving paper with ID {paper_id}: {str(e)}")


async def get_paper_by_arxiv_id(arxiv_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a paper from the Supabase database by its arXiv ID.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        
    Returns:
        The paper data as a dictionary, or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the paper
    """
    try:
        response = supabase.table("papers").select("*").eq("arxiv_id", arxiv_id).execute()
        
        if len(response.data) == 0:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving paper with arXiv ID {arxiv_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving paper with arXiv ID {arxiv_id}: {str(e)}")


async def get_paper_by_source(source_url: str, source_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a paper from the Supabase database by its source URL and type.
    
    Args:
        source_url: The source URL of the paper
        source_type: The source type ("arxiv" or "pdf")
        
    Returns:
        The paper data as a dictionary, or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the paper
    """
    try:
        response = supabase.table("papers").select("*").eq("source_url", source_url).eq("source_type", source_type).execute()
        
        if len(response.data) == 0:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving paper with source URL {source_url}: {str(e)}")
        raise SupabaseError(f"Error retrieving paper with source URL {source_url}: {str(e)}")
        

async def insert_paper(paper_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a paper into the Supabase database.
    
    Args:
        paper_data: The paper data to insert
        
    Returns:
        The inserted paper data
        
    Raises:
        SupabaseError: If there's an error inserting the paper
    """
    try:
        # Ensure source_type is set if not provided
        if "source_type" not in paper_data:
            paper_data["source_type"] = SourceType.ARXIV
            
        # For arXiv papers, ensure source_url is set if not provided
        if paper_data["source_type"] == SourceType.ARXIV and "source_url" not in paper_data and "arxiv_id" in paper_data:
            paper_data["source_url"] = f"https://arxiv.org/abs/{paper_data['arxiv_id']}"
            
        response = supabase.table("papers").insert(paper_data).execute()
        
        if len(response.data) == 0:
            raise SupabaseError("Failed to insert paper: No data returned")
            
        logger.info(f"Paper inserted with ID: {response.data[0]['id']}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error inserting paper: {str(e)}")
        raise SupabaseError(f"Error inserting paper: {str(e)}")


async def update_paper(paper_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a paper in the Supabase database.
    
    Args:
        paper_id: The UUID of the paper to update
        update_data: The data to update
        
    Returns:
        The updated paper data
        
    Raises:
        SupabaseError: If there's an error updating the paper
    """
    try:
        response = supabase.table("papers").update(update_data).eq("id", str(paper_id)).execute()
        
        if len(response.data) == 0:
            raise SupabaseError(f"Failed to update paper with ID {paper_id}: No data returned")
            
        logger.info(f"Paper updated with ID: {response.data[0]['id']}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error updating paper with ID {paper_id}: {str(e)}")
        raise SupabaseError(f"Error updating paper with ID {paper_id}: {str(e)}")


async def list_papers(user_id: str) -> List[Dict[str, Any]]:
    """
    List papers for a specific user from the Supabase database.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        List of papers associated with the user
        
    Raises:
        SupabaseError: If there's an error listing papers
    """
    try:
        # First get the paper IDs for this user
        user_papers_response = (
            supabase.table("users_papers")
            .select("paper_id")
            .eq("user_id", user_id)
            .execute()
        )
        
        if not user_papers_response.data:
            return []
            
        # Extract paper IDs
        paper_ids = [up["paper_id"] for up in user_papers_response.data]
        
        # Then get the actual papers
        papers_response = (
            supabase.table("papers")
            .select("*")
            .in_("id", paper_ids)
            .order("publication_date", desc=True)
            .execute()
        )
        
        return papers_response.data
    except Exception as e:
        logger.error(f"Error listing papers for user {user_id}: {str(e)}")
        raise SupabaseError(f"Error listing papers for user {user_id}: {str(e)}")


async def add_paper_to_user(user_id: str, paper_id: str) -> None:
    """
    Associate a paper with a user in the users_papers table.
    
    Args:
        user_id: The ID of the user
        paper_id: The ID of the paper
        
    Raises:
        SupabaseError: If there's an error adding the association
    """
    try:
        response = supabase.table("users_papers").insert({
            "user_id": user_id,
            "paper_id": paper_id
        }).execute()
        logger.info(f"Added paper {paper_id} to user {user_id}")
    except Exception as e:
        logger.error(f"Error adding paper {paper_id} to user {user_id}: {str(e)}")
        raise SupabaseError(f"Error adding paper {paper_id} to user {user_id}: {str(e)}")


async def create_conversation(conversation_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a conversation in the Supabase database.
    
    Args:
        conversation_data: The conversation data to insert, should include:
            - id: Unique identifier for the conversation
            - user_id: ID of the user who owns the conversation
            - paper_id: ID of the paper the conversation is about (new field)
        
    Returns:
        The created conversation data
        
    Raises:
        SupabaseError: If there's an error creating the conversation
    """
    try:
        # Ensure paper_id is included in the conversation data
        if "paper_id" not in conversation_data:
            # For backward compatibility, if paper_id is not provided, use the id as paper_id
            conversation_data["paper_id"] = conversation_data["id"]
            logger.info(f"Using conversation ID as paper_id: {conversation_data['id']}")
        
        response = supabase.table("user_conversations").insert(conversation_data).execute()
        
        if len(response.data) == 0:
            raise SupabaseError("Failed to create conversation: No data returned")
            
        logger.info(f"Conversation created with ID: {response.data[0]['id']}, paper_id: {conversation_data['paper_id']}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise SupabaseError(f"Error creating conversation: {str(e)}")


async def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a conversation from the Supabase database by its ID.
    
    Args:
        conversation_id: The ID of the conversation
        
    Returns:
        The conversation data as a dictionary, or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the conversation
    """
    try:
        response = supabase.table("user_conversations").select("*").eq("id", conversation_id).execute()
        
        if len(response.data) == 0:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving conversation with ID {conversation_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving conversation with ID {conversation_id}: {str(e)}")


async def insert_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a message into the Supabase database.
    
    Args:
        message_data: The message data to insert
        
    Returns:
        The inserted message data
        
    Raises:
        SupabaseError: If there's an error inserting the message
    """
    try:
        response = supabase.table("messages").insert(message_data).execute()
        
        if len(response.data) == 0:
            raise SupabaseError("Failed to insert message: No data returned")
            
        logger.info(f"Message inserted with ID: {response.data[0]['id']}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error inserting message: {str(e)}")
        raise SupabaseError(f"Error inserting message: {str(e)}")


async def get_conversation_messages(conversation_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all messages for a specific conversation from the Supabase database.
    
    Args:
        conversation_id: The ID of the conversation
        
    Returns:
        List of messages for the conversation, ordered by creation timestamp
        
    Raises:
        SupabaseError: If there's an error retrieving the messages
    """
    try:
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        
        logger.info(f"Retrieved {len(response.data)} messages for conversation {conversation_id}")
        return response.data
    except Exception as e:
        logger.error(f"Error retrieving messages for conversation {conversation_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving messages for conversation {conversation_id}: {str(e)}")


async def get_user_paper_conversations(user_id: str, paper_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all conversations for a specific user and paper from the Supabase database.
    
    Args:
        user_id: The ID of the user
        paper_id: The ID of the paper
        
    Returns:
        List of conversations for the user and paper, ordered by creation timestamp
        
    Raises:
        SupabaseError: If there's an error retrieving the conversations
    """
    try:
        response = supabase.table("user_conversations").select("*").eq("user_id", user_id).eq("paper_id", paper_id).order("created_at", desc=True).execute()
        
        logger.info(f"Retrieved {len(response.data)} conversations for user {user_id} and paper {paper_id}")
        return response.data
    except Exception as e:
        logger.error(f"Error retrieving conversations for user {user_id} and paper {paper_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving conversations for user {user_id} and paper {paper_id}: {str(e)}")


async def get_paper_full_text(paper_id: UUID) -> Optional[str]:
    """
    Retrieve the full text of a paper from the Supabase database.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        The full text of the paper, or None if not found or not processed
        
    Raises:
        SupabaseError: If there's an error retrieving the paper
    """
    try:
        # Get the paper from the database
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"Paper with ID {paper_id} not found")
            return None
            
        # Check if the paper has been processed
        if not paper.get("full_text"):
            logger.warning(f"Paper with ID {paper_id} has not been processed yet")
            return None
            
        # Get the full text from the paper
        full_text = paper.get("full_text", "")
        
        # If the full text is too short (likely just a preview), try to reconstruct from chunks
        if len(full_text) < 1500:  # Assuming 1000 chars is the preview + some buffer
            logger.info(f"Full text for paper {paper_id} is too short, attempting to reconstruct from chunks")
            
            try:
                # Query the Pinecone index to get all chunks for this paper
                from app.services.pinecone_service import get_all_paper_chunks
                
                chunks = await get_all_paper_chunks(paper_id)
                if chunks:
                    # Reconstruct the full text from chunks
                    reconstructed_text = "\n\n".join([chunk.get("text", "") for chunk in chunks])
                    logger.info(f"Successfully reconstructed full text for paper {paper_id} from {len(chunks)} chunks")
                    return reconstructed_text
            except Exception as e:
                logger.warning(f"Error reconstructing full text from chunks: {str(e)}")
                # Continue with the preview if reconstruction fails
        
        logger.info(f"Retrieved full text for paper {paper_id} ({len(full_text)} characters)")
        return full_text
    except Exception as e:
        logger.error(f"Error retrieving full text for paper with ID {paper_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving full text for paper with ID {paper_id}: {str(e)}") 