from fastapi import APIRouter, Depends, HTTPException, status
from app.database.supabase_client import supabase
from app.services.email_service import send_waiting_list_confirmation
from app.core.logger import get_logger
from app.dependencies import get_supabase_client, rate_limit
from pydantic import BaseModel, EmailStr
from typing import Dict, Any
from fastapi.requests import Request

router = APIRouter()
logger = get_logger(__name__)

class WaitingListRequest(BaseModel):
    """Request model for joining the waiting list."""
    email: EmailStr

@router.post("/join", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def join_waiting_list(
    request: Request,
    waiting_list_request: WaitingListRequest,
    _: Any = Depends(rate_limit),
    supabase_client = Depends(get_supabase_client)
):
    """
    Add an email to the waiting list and send a confirmation email.
    
    Args:
        request: The FastAPI request object
        waiting_list_request: The request containing the email
        _: Rate limiting dependency
        supabase_client: The Supabase client
        
    Returns:
        A dictionary with a success message
        
    Raises:
        HTTPException: If there's an error adding the email to the waiting list
    """
    try:
        email = waiting_list_request.email
        
        # Check if the email already exists in the waiting list
        response = supabase_client.table("waiting_list").select("*").eq("email", email).execute()
        
        if len(response.data) > 0:
            # Email already exists, return success without adding again
            logger.info(f"Email {email} already exists in the waiting list")
            return {"message": "You're already on our waiting list!"}
        
        # Add the email to the waiting list
        response = supabase_client.table("waiting_list").insert({"email": email}).execute()
        
        if len(response.data) == 0:
            logger.error(f"Failed to add email {email} to the waiting list")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add email to the waiting list"
            )
            
        # Send confirmation email
        email_sent = await send_waiting_list_confirmation(email)
        
        if not email_sent:
            logger.warning(f"Failed to send confirmation email to {email}, but they were added to the waiting list")
            
        logger.info(f"Successfully added email {email} to the waiting list")
        return {"message": "Thank you for joining our waiting list!"}
        
    except Exception as e:
        logger.error(f"Error adding email to waiting list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding email to waiting list: {str(e)}"
        ) 