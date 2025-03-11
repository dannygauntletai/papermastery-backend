from fastapi import Depends, HTTPException, status
from app.database.supabase_client import supabase
from app.core.logger import get_logger
from typing import Dict, Any

logger = get_logger(__name__)

async def get_supabase_client():
    """
    Dependency to get the Supabase client.
    
    Returns:
        Supabase client instance
    """
    return supabase

async def validate_environment(env_vars: Dict[str, Any] = Depends()):
    """
    Dependency to validate that required environment variables are set.
    This is mainly for demonstration as we've already validated in config.py.
    
    Raises:
        HTTPException: If any environment variables are missing
    """
    # Note: We've already validated in config.py, but this is a fallback
    from app.core.config import SUPABASE_URL, SUPABASE_KEY, PINECONE_API_KEY
    
    missing_vars = []
    
    if not SUPABASE_URL:
        missing_vars.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing_vars.append("SUPABASE_KEY")
    if not PINECONE_API_KEY:
        missing_vars.append("PINECONE_API_KEY")
        
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server configuration error: Missing environment variables: {', '.join(missing_vars)}"
        )
        
    return True 