from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from app.core.logger import get_logger
from app.core.exceptions import SupabaseError
from uuid import UUID
from typing import Dict, Any, Optional, List
from app.api.v1.models import SourceType
import re

logger = get_logger(__name__)

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    raise SupabaseError(f"Failed to initialize Supabase client: {str(e)}")


async def get_supabase_client() -> Client:
    """
    Get the Supabase client. This function exists to maintain consistency 
    with other functions that might need an async client in the future.
    
    Returns:
        The initialized Supabase client
    """
    return supabase


async def get_paper_by_id(paper_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a paper from the Supabase database by its ID.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        The paper data as a dictionary, or None if not found
    """
    try:
        client = await get_supabase_client()
        response = (
            client.table("papers")
            .select("*")
            .eq("id", paper_id)
            .execute()
        )
        
        data = response.data
        return data[0] if data else None
    except Exception as e:
        logger.error(f"Error retrieving paper with ID {paper_id}: {str(e)}")
        return None


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
        
        if not response.data:
            # For arXiv papers, also try to match by arXiv ID
            if source_type == "arxiv" and "arxiv.org" in source_url:
                # Extract arXiv ID from URL
                match = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', source_url)
                if match:
                    arxiv_id = match.group(1)
                    # Remove version if present
                    if 'v' in arxiv_id:
                        arxiv_id = arxiv_id.split('v')[0]
                    
                    # Try to find by arXiv ID
                    response = supabase.table("papers").select("*").eq("arxiv_id", arxiv_id).execute()
            
            if not response.data:
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
        paper = await get_paper_by_id(str(paper_id))
        if not paper:
            logger.warning(f"Paper with ID {paper_id} not found")
            return None
            
        # Check if the paper has been processed
        if not paper.get("full_text"):
            logger.warning(f"Paper with ID {paper_id} has not been processed yet")
            return None
            
        # Get the full text from the paper
        full_text = paper.get("full_text", "")
        
        # Return the full text directly
        return full_text
    except Exception as e:
        logger.error(f"Error retrieving full text for paper with ID {paper_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving full text for paper with ID {paper_id}: {str(e)}")


# ==================== Consulting System CRUD Operations ====================

async def create_researcher(researcher_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new researcher profile in the database.
    
    Args:
        researcher_data: Data for the researcher profile
        
    Returns:
        The created researcher data
        
    Raises:
        SupabaseError: If there's an error creating the researcher
    """
    try:
        response = supabase.table("researchers").insert(researcher_data).execute()
        
        if not response.data:
            logger.error("Failed to create researcher profile")
            raise SupabaseError("Failed to create researcher profile")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating researcher profile: {str(e)}")
        raise SupabaseError(f"Error creating researcher profile: {str(e)}")


async def get_researcher_by_id(researcher_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Retrieve a researcher by ID.
    
    Args:
        researcher_id: The UUID of the researcher
        
    Returns:
        The researcher data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the researcher
    """
    try:
        response = supabase.table("researchers").select("*").eq("id", str(researcher_id)).execute()
        
        if not response.data:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving researcher with ID {researcher_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving researcher with ID {researcher_id}: {str(e)}")


async def get_researcher_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a researcher by email.
    
    Args:
        email: The email of the researcher
        
    Returns:
        The researcher data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the researcher
    """
    try:
        response = supabase.table("researchers").select("*").eq("email", email).execute()
        
        if not response.data:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving researcher with email {email}: {str(e)}")
        raise SupabaseError(f"Error retrieving researcher with email {email}: {str(e)}")


async def update_researcher(researcher_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a researcher profile.
    
    Args:
        researcher_id: The UUID of the researcher
        update_data: The data to update
        
    Returns:
        The updated researcher data
        
    Raises:
        SupabaseError: If there's an error updating the researcher
    """
    try:
        response = supabase.table("researchers").update(update_data).eq("id", str(researcher_id)).execute()
        
        if not response.data:
            logger.error(f"Failed to update researcher with ID {researcher_id}")
            raise SupabaseError(f"Failed to update researcher with ID {researcher_id}")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error updating researcher with ID {researcher_id}: {str(e)}")
        raise SupabaseError(f"Error updating researcher with ID {researcher_id}: {str(e)}")


async def get_primary_researcher_for_paper(paper_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Get the primary researcher associated with a paper.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        The researcher data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the researcher
    """
    try:
        # First, get the paper to check if it has a primary_researcher_id
        paper = await get_paper_by_id(str(paper_id))
        if not paper:
            logger.error(f"Paper with ID {paper_id} not found")
            return None
            
        if paper.get("primary_researcher_id"):
            return await get_researcher_by_id(UUID(paper["primary_researcher_id"]))
            
        # If no primary_researcher_id is set, try to find one based on the paper's authors
        if paper.get("authors"):
            for author in paper["authors"]:
                # Try to find a researcher with a matching name
                name = author.get("name", "")
                if name:
                    response = supabase.table("researchers").select("*").ilike("name", f"%{name}%").execute()
                    if response.data:
                        return response.data[0]
        
        return None
    except Exception as e:
        logger.error(f"Error retrieving primary researcher for paper {paper_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving primary researcher for paper {paper_id}: {str(e)}")


async def create_subscription(subscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new subscription.
    
    Args:
        subscription_data: Data for the subscription
        
    Returns:
        The created subscription data
        
    Raises:
        SupabaseError: If there's an error creating the subscription
    """
    try:
        response = supabase.table("subscriptions").insert(subscription_data).execute()
        
        if not response.data:
            logger.error("Failed to create subscription")
            raise SupabaseError("Failed to create subscription")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        raise SupabaseError(f"Error creating subscription: {str(e)}")


async def get_subscription_by_id(subscription_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Get a subscription by ID.
    
    Args:
        subscription_id: UUID of the subscription
        
    Returns:
        Subscription data or None if not found
    """
    try:
        client = await get_supabase_client()
        response = (
            client.table("subscriptions")
            .select("*")
            .eq("id", str(subscription_id))
            .execute()
        )
        
        data = response.data
        return data[0] if data else None
    except Exception as e:
        logger.error(f"Error getting subscription by ID {subscription_id}: {str(e)}")
        return None


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a user by ID.
    
    Args:
        user_id: ID of the user
        
    Returns:
        User data or None if not found
    """
    try:
        client = await get_supabase_client()
        response = (
            client.table("users")
            .select("*")
            .eq("id", user_id)
            .execute()
        )
        
        data = response.data
        return data[0] if data else None
    except Exception as e:
        logger.error(f"Error getting user by ID {user_id}: {str(e)}")
        return None


async def get_user_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user's active subscription.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        The subscription data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the subscription
    """
    try:
        response = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
        
        if not response.data:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving subscription for user {user_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving subscription for user {user_id}: {str(e)}")


async def update_subscription(subscription_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a subscription.
    
    Args:
        subscription_id: The UUID of the subscription
        update_data: The data to update
        
    Returns:
        The updated subscription data
        
    Raises:
        SupabaseError: If there's an error updating the subscription
    """
    try:
        response = supabase.table("subscriptions").update(update_data).eq("id", str(subscription_id)).execute()
        
        if not response.data:
            logger.error(f"Failed to update subscription with ID {subscription_id}")
            raise SupabaseError(f"Failed to update subscription with ID {subscription_id}")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error updating subscription with ID {subscription_id}: {str(e)}")
        raise SupabaseError(f"Error updating subscription with ID {subscription_id}: {str(e)}")


async def create_outreach_request(outreach_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new outreach request.
    
    Args:
        outreach_data: Data for the outreach request
        
    Returns:
        The created outreach request data
        
    Raises:
        SupabaseError: If there's an error creating the outreach request
    """
    try:
        response = supabase.table("outreach_requests").insert(outreach_data).execute()
        
        if not response.data:
            logger.error("Failed to create outreach request")
            raise SupabaseError("Failed to create outreach request")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating outreach request: {str(e)}")
        raise SupabaseError(f"Error creating outreach request: {str(e)}")


async def get_outreach_request_by_id(request_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Retrieve an outreach request by ID.
    
    Args:
        request_id: The UUID of the outreach request
        
    Returns:
        The outreach request data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the outreach request
    """
    try:
        response = supabase.table("outreach_requests").select("*").eq("id", str(request_id)).execute()
        
        if not response.data:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving outreach request with ID {request_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving outreach request with ID {request_id}: {str(e)}")


async def get_outreach_requests_by_researcher_email(email: str) -> List[Dict[str, Any]]:
    """
    Retrieve outreach requests for a researcher by email.
    
    Args:
        email: The email of the researcher
        
    Returns:
        A list of outreach request data
        
    Raises:
        SupabaseError: If there's an error retrieving the outreach requests
    """
    try:
        response = supabase.table("outreach_requests").select("*").eq("researcher_email", email).execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error retrieving outreach requests for researcher {email}: {str(e)}")
        raise SupabaseError(f"Error retrieving outreach requests for researcher {email}: {str(e)}")


async def update_outreach_request(request_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an outreach request.
    
    Args:
        request_id: The UUID of the outreach request
        update_data: The data to update
        
    Returns:
        The updated outreach request data
        
    Raises:
        SupabaseError: If there's an error updating the outreach request
    """
    try:
        response = supabase.table("outreach_requests").update(update_data).eq("id", str(request_id)).execute()
        
        if not response.data:
            logger.error(f"Failed to update outreach request with ID {request_id}")
            raise SupabaseError(f"Failed to update outreach request with ID {request_id}")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error updating outreach request with ID {request_id}: {str(e)}")
        raise SupabaseError(f"Error updating outreach request with ID {request_id}: {str(e)}")


async def create_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new consultation session.
    
    Args:
        session_data: Data for the session
        
    Returns:
        The created session data
        
    Raises:
        SupabaseError: If there's an error creating the session
    """
    try:
        response = supabase.table("sessions").insert(session_data).execute()
        
        if not response.data:
            logger.error("Failed to create session")
            raise SupabaseError("Failed to create session")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise SupabaseError(f"Error creating session: {str(e)}")


async def get_session_by_id(session_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Retrieve a session by ID.
    
    Args:
        session_id: The UUID of the session
        
    Returns:
        The session data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the session
    """
    try:
        response = supabase.table("sessions").select("*").eq("id", str(session_id)).execute()
        
        if not response.data:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving session with ID {session_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving session with ID {session_id}: {str(e)}")


async def get_sessions_by_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve sessions for a user.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        A list of session data
        
    Raises:
        SupabaseError: If there's an error retrieving the sessions
    """
    try:
        response = supabase.table("sessions").select("*").eq("user_id", user_id).order("start_time", options={"ascending": False}).execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error retrieving sessions for user {user_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving sessions for user {user_id}: {str(e)}")


async def get_sessions_by_researcher(researcher_id: UUID) -> List[Dict[str, Any]]:
    """
    Retrieve sessions for a researcher.
    
    Args:
        researcher_id: The UUID of the researcher
        
    Returns:
        A list of session data
        
    Raises:
        SupabaseError: If there's an error retrieving the sessions
    """
    try:
        response = supabase.table("sessions").select("*").eq("researcher_id", str(researcher_id)).order("start_time", options={"ascending": False}).execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error retrieving sessions for researcher {researcher_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving sessions for researcher {researcher_id}: {str(e)}")


async def update_session(session_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a session.
    
    Args:
        session_id: The UUID of the session
        update_data: The data to update
        
    Returns:
        The updated session data
        
    Raises:
        SupabaseError: If there's an error updating the session
    """
    try:
        response = supabase.table("sessions").update(update_data).eq("id", str(session_id)).execute()
        
        if not response.data:
            logger.error(f"Failed to update session with ID {session_id}")
            raise SupabaseError(f"Failed to update session with ID {session_id}")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error updating session with ID {session_id}: {str(e)}")
        raise SupabaseError(f"Error updating session with ID {session_id}: {str(e)}")


async def create_payment(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new payment record.
    
    Args:
        payment_data: Data for the payment
        
    Returns:
        The created payment data
        
    Raises:
        SupabaseError: If there's an error creating the payment
    """
    try:
        response = supabase.table("payments").insert(payment_data).execute()
        
        if not response.data:
            logger.error("Failed to create payment")
            raise SupabaseError("Failed to create payment")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        raise SupabaseError(f"Error creating payment: {str(e)}")


async def get_payment_by_id(payment_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Retrieve a payment by ID.
    
    Args:
        payment_id: The UUID of the payment
        
    Returns:
        The payment data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the payment
    """
    try:
        response = supabase.table("payments").select("*").eq("id", str(payment_id)).execute()
        
        if not response.data:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving payment with ID {payment_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving payment with ID {payment_id}: {str(e)}")


async def get_payments_by_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve payments for a user.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        A list of payment data
        
    Raises:
        SupabaseError: If there's an error retrieving the payments
    """
    try:
        response = supabase.table("payments").select("*").eq("user_id", user_id).order("created_at", options={"ascending": False}).execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error retrieving payments for user {user_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving payments for user {user_id}: {str(e)}")


async def get_payment_by_transaction_id(transaction_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a payment by its transaction ID (e.g., Stripe payment intent ID).
    
    Args:
        transaction_id: The external transaction ID
        
    Returns:
        The payment data or None if not found
    """
    try:
        client = await get_supabase_client()
        response = (
            client.table("payments")
            .select("*")
            .eq("transaction_id", transaction_id)
            .execute()
        )
        
        data = response.data
        return data[0] if data else None
    except Exception as e:
        logger.error(f"Error retrieving payment with transaction ID {transaction_id}: {str(e)}")
        return None


async def update_payment(payment_id: UUID, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a payment.
    
    Args:
        payment_id: The UUID of the payment
        update_data: The data to update
        
    Returns:
        The updated payment data
        
    Raises:
        SupabaseError: If there's an error updating the payment
    """
    try:
        response = supabase.table("payments").update(update_data).eq("id", str(payment_id)).execute()
        
        if not response.data:
            logger.error(f"Failed to update payment with ID {payment_id}")
            raise SupabaseError(f"Failed to update payment with ID {payment_id}")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error updating payment with ID {payment_id}: {str(e)}")
        raise SupabaseError(f"Error updating payment with ID {payment_id}: {str(e)}")


async def create_review(review_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new review.
    
    Args:
        review_data: Data for the review
        
    Returns:
        The created review data
        
    Raises:
        SupabaseError: If there's an error creating the review
    """
    try:
        response = supabase.table("reviews").insert(review_data).execute()
        
        if not response.data:
            logger.error("Failed to create review")
            raise SupabaseError("Failed to create review")
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error creating review: {str(e)}")
        raise SupabaseError(f"Error creating review: {str(e)}")


async def get_review_by_id(review_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Retrieve a review by ID.
    
    Args:
        review_id: The UUID of the review
        
    Returns:
        The review data or None if not found
        
    Raises:
        SupabaseError: If there's an error retrieving the review
    """
    try:
        response = supabase.table("reviews").select("*").eq("id", str(review_id)).execute()
        
        if not response.data:
            return None
            
        return response.data[0]
    except Exception as e:
        logger.error(f"Error retrieving review with ID {review_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving review with ID {review_id}: {str(e)}")


async def get_reviews_by_researcher(researcher_id: UUID) -> List[Dict[str, Any]]:
    """
    Retrieve reviews for a researcher.
    
    Args:
        researcher_id: The UUID of the researcher
        
    Returns:
        A list of review data
        
    Raises:
        SupabaseError: If there's an error retrieving the reviews
    """
    try:
        response = supabase.table("reviews").select("*").eq("researcher_id", str(researcher_id)).order("created_at", options={"ascending": False}).execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error retrieving reviews for researcher {researcher_id}: {str(e)}")
        raise SupabaseError(f"Error retrieving reviews for researcher {researcher_id}: {str(e)}") 