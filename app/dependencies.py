from fastapi import Depends, HTTPException, status, Request
from app.database.supabase_client import supabase
from app.core.logger import get_logger
from typing import Dict, Any
import time
from datetime import datetime, timedelta

logger = get_logger(__name__)

# Simple in-memory rate limiting store
# In production, you would use Redis or another distributed cache
rate_limit_store = {}

async def get_supabase_client():
    """
    Dependency to get the Supabase client.
    
    Returns:
        Supabase client instance
    """
    return supabase

async def validate_environment():
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

async def rate_limit(request: Request, limit: int = 5, window: int = 60):
    """
    Dependency to enforce rate limiting on endpoints.
    
    Args:
        request: The FastAPI request object
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        
    Raises:
        HTTPException: If rate limit is exceeded
        
    Returns:
        True if rate limit is not exceeded
    """
    # Get client IP as identifier (in production, use authenticated user ID)
    client_id = request.client.host if request.client else "unknown"
    
    # Clean up expired entries
    current_time = time.time()
    for key in list(rate_limit_store.keys()):
        if current_time - rate_limit_store[key]["timestamp"] > window:
            del rate_limit_store[key]
    
    # Check if client has any requests recorded
    if client_id in rate_limit_store:
        client_data = rate_limit_store[client_id]
        # If within window, increment count
        if current_time - client_data["timestamp"] < window:
            client_data["count"] += 1
            # If exceeding limit, raise exception
            if client_data["count"] > limit:
                reset_time = datetime.fromtimestamp(client_data["timestamp"] + window)
                reset_seconds = int((reset_time - datetime.now()).total_seconds())
                logger.warning(f"Rate limit exceeded for client {client_id}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {reset_seconds} seconds.",
                    headers={"Retry-After": str(reset_seconds)}
                )
        else:
            # If outside window, reset count
            client_data["count"] = 1
            client_data["timestamp"] = current_time
    else:
        # First request from this client
        rate_limit_store[client_id] = {
            "count": 1,
            "timestamp": current_time
        }
    
    return True

async def get_current_user(request: Request) -> str:
    """
    Dependency to get the current authenticated user.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        str: The user ID
        
    Raises:
        HTTPException: If user is not authenticated
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify the JWT token using Supabase
        token = auth_header.split(" ")[1]
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