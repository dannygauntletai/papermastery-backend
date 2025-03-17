from fastapi import Depends, HTTPException, status, Header, Request
from typing import Optional
import logging
from app.database.supabase_client import supabase

logger = logging.getLogger(__name__)

async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract and validate the user ID from the authorization header.
    Verifies the JWT token using Supabase and extracts the user ID.
    
    Returns:
        str: The user ID
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not authorization:
        # For development only - return a mock user ID
        logger.warning("No authorization header provided, using mock user ID")
        return "mock-user-123"
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Extract the token from the header
        token = authorization.split(" ")[1]
        
        # Verify the JWT token using Supabase
        user = supabase.auth.get_user(token)
        
        # Access the user ID from the correct location in the response
        user_id = user.user.id
        if not user_id:
            raise ValueError("User ID not found in response")
            
        return user_id
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) 