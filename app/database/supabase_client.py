from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from app.core.logger import get_logger
from app.core.exceptions import SupabaseError

logger = get_logger(__name__)

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    raise SupabaseError(f"Failed to initialize Supabase client: {str(e)}")

async def get_paper_by_arxiv_id(arxiv_id: str) -> dict:
    """
    Retrieve a paper from the Supabase database by its arXiv ID.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        
    Returns:
        The paper data as a dictionary
        
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
        
async def insert_paper(paper_data: dict) -> dict:
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