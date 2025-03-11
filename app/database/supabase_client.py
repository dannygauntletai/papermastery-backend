from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from app.core.logger import get_logger
from app.core.exceptions import SupabaseError
from uuid import UUID
from typing import Dict, Any, Optional, List

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


async def list_papers() -> List[Dict[str, Any]]:
    """
    List all papers in the Supabase database.
    
    Returns:
        List of papers
        
    Raises:
        SupabaseError: If there's an error listing papers
    """
    try:
        response = supabase.table("papers").select("*").order("publication_date", desc=True).execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error listing papers: {str(e)}")
        raise SupabaseError(f"Error listing papers: {str(e)}") 