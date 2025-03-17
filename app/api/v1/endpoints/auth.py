from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.logger import get_logger
from app.core.auth import get_current_user
from app.api.v1.models import ResearcherCreate, ResearcherResponse
from app.services.email_service import verify_registration_token
from app.services.consulting_service import (
    create_or_update_researcher_profile, 
    handle_researcher_response
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register-researcher", response_model=ResearcherResponse)
async def register_researcher(
    researcher: ResearcherCreate,
    token: str
) -> ResearcherResponse:
    """
    Register a new researcher using a registration token.
    
    This endpoint validates the registration token sent via email and creates 
    a new researcher profile. It also updates the associated outreach request status.
    
    Args:
        researcher: Researcher profile data
        token: Registration token from the invitation email
        
    Returns:
        ResearcherResponse object with the created researcher profile
    """
    try:
        # Verify token
        try:
            payload = verify_registration_token(token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or expired token: {str(e)}"
            )
            
        # Extract data from token
        researcher_email = payload.get("email")
        outreach_id = payload.get("outreach_id")
        
        if not researcher_email or not outreach_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing required data"
            )
            
        # Ensure the email matches the token
        if researcher_email != researcher.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email does not match the token"
            )
            
        # Create researcher profile
        researcher_data = researcher.dict()
        researcher_profile = await create_or_update_researcher_profile(researcher_data)
        
        if not researcher_profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create researcher profile"
            )
            
        # Update outreach request
        await handle_researcher_response(outreach_id, "accepted")
        
        return ResearcherResponse(
            success=True,
            message="Researcher profile created successfully",
            data=researcher_profile
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error registering researcher: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering researcher: {str(e)}"
        ) 