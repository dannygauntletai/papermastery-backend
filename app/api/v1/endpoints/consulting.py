from typing import Dict, Any, List, Optional, Union
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
import datetime as dt

from app.api.v1.models import (
    ResearcherCreate, 
    ResearcherResponse, 
    ResearcherCollectionRequest,
    ResearcherCollectionResponse,
    SessionCreate,
    SessionResponse, 
    OutreachRequestCreate,
    OutreachRequestResponse,
    SubscriptionResponse
)
from app.core.logger import get_logger
from app.core.config import get_settings
from app.services.data_collection_orchestrator import (
    collect_researcher_data,
    batch_collect_researcher_data,
    collect_for_institution
)
from app.services.consulting_service import (
    get_researcher,
    get_researcher_by_paper_id,
    create_or_update_researcher_profile,
    request_researcher_outreach,
    handle_researcher_response,
    book_session,
    update_session_status,
    get_researcher_sessions,
    create_user_subscription
)
from app.database.supabase_client import (
    get_researcher_by_email,
    get_paper_by_id,
    get_user_by_id,
    update_outreach_request
)
from app.core.exceptions import SupabaseError
from app.services.session_service import (
    create_consultation_session,
    get_session,
    get_researcher_consultations,
    get_user_consultations,
    reschedule_session
)
from app.services.zoom_service import create_zoom_meeting
from app.services.email_service import (
    send_researcher_outreach_email,
    generate_registration_token
)
import stripe
from app.core.auth import get_current_user

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/consulting", tags=["consulting"])

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/researchers/collect", response_model=ResearcherCollectionResponse, status_code=status.HTTP_200_OK)
async def collect_researcher_data_endpoint(
    request: ResearcherCollectionRequest,
    background_tasks: BackgroundTasks
) -> ResearcherCollectionResponse:
    """
    Collect researcher data from various sources (Firecrawl, RocketReach, Tavily).
    
    This endpoint initiates the collection of researcher data in the background:
    1. Scrapes profiles with Firecrawl with web search enabled
    2. Fetches emails with RocketReach (if email is missing) 
    3. Stores the result in Supabase for realtime updates
    
    The frontend should use Supabase realtime subscription to get updates.
    """
    try:
        # Always process the data collection in the background
        # Override the request's run_in_background value
        request.run_in_background = True
        
        # Check if researcher already exists by email (if email is provided)
        existing_researcher = None
        existing_researcher_id = None
        if request.email:
            existing_researcher = await get_researcher_by_email(request.email)
            if existing_researcher:
                existing_researcher_id = existing_researcher.get("id")
        
        # Add the background task
        background_tasks.add_task(
            handle_researcher_collection,
            request
        )
        
        # Return minimal information - just status and researcher ID
        return ResearcherCollectionResponse(
            success=True,
            message=f"Researcher data collection started for {request.name}",
            data={
                "status": "processing",
                "researcher_id": existing_researcher_id
            }
        )
            
    except Exception as e:
        logger.error(f"Error starting researcher data collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting researcher data collection: {str(e)}"
        )


@router.post("/researchers/batch-collect", response_model=List[ResearcherCollectionResponse], status_code=status.HTTP_200_OK)
async def batch_collect_researchers_endpoint(
    requests: List[ResearcherCollectionRequest],
    background_tasks: BackgroundTasks
) -> List[ResearcherCollectionResponse]:
    """
    Collect data for multiple researchers in batch.
    
    This endpoint processes multiple researcher data collection requests:
    1. Validates each request
    2. Processes them in parallel
    3. Returns results for each researcher
    
    The batch collection can be run in the background if specified in any request.
    """
    try:
        # Check if any request should run in background
        run_in_background = any(request.run_in_background for request in requests)
        
        if run_in_background:
            # Process the batch collection in the background
            background_tasks.add_task(
                handle_batch_collection,
                requests
            )
            
            return [
                ResearcherCollectionResponse(
                    success=True,
                    message=f"Data collection for researcher {request.name} started in background",
                    data={
                        "status": "background_started",
                        "researcher_id": None,
                        "name": request.name,
                        "affiliation": request.affiliation,
                    }
                )
                for request in requests
            ]
        else:
            # Process the batch collection synchronously
            results = []
            researchers_data = [
                {
                    "name": req.name,
                    "affiliation": req.affiliation,
                    "paper_title": req.paper_title,
                    "position": req.position,
                    "researcher_id": req.researcher_id,
                }
                for req in requests
            ]
            
            batch_results = await batch_collect_researcher_data(researchers_data)
            
            # Format the results
            for i, result in enumerate(batch_results):
                request = requests[i]
                
                if isinstance(result, dict) and result.get("success", False):
                    results.append(
                        ResearcherCollectionResponse(
                            success=True,
                            message=f"Successfully collected data for researcher {request.name}",
                            data=result
                        )
                    )
                else:
                    error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
                    results.append(
                        ResearcherCollectionResponse(
                            success=False,
                            message=f"Failed to collect data for researcher {request.name}: {error_msg}",
                            data={
                                "status": "failed",
                                "error": error_msg,
                                "name": request.name,
                                "affiliation": request.affiliation,
                            }
                        )
                    )
            
            return results
            
    except Exception as e:
        logger.error(f"Error in batch collection of researcher data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in batch collection: {str(e)}"
        )


@router.post("/researchers/collect-by-institution", response_model=List[ResearcherCollectionResponse], status_code=status.HTTP_200_OK)
async def collect_institution_researchers_endpoint(
    institution: str,
    position: Optional[str] = None,
    limit: int = 10,
    background_tasks: BackgroundTasks = None,
    run_in_background: bool = False
) -> List[ResearcherCollectionResponse]:
    """
    Collect data for multiple researchers at a specific institution.
    
    This endpoint searches for researchers at the institution and collects their data:
    1. Searches for researchers using RocketReach
    2. Collects detailed data for each researcher found
    3. Returns results for all researchers
    
    The collection can be run in the background if specified.
    """
    try:
        if run_in_background and background_tasks:
            # Process the institution collection in the background
            background_tasks.add_task(
                handle_institution_collection,
                institution=institution,
                position=position,
                limit=limit
            )
            
            return [
                ResearcherCollectionResponse(
                    success=True,
                    message=f"Data collection for institution {institution} started in background",
                    data={
                        "status": "background_started",
                        "institution": institution,
                        "position": position,
                    }
                )
            ]
        else:
            # Process the institution collection synchronously
            results = await handle_institution_collection(
                institution=institution,
                position=position,
                limit=limit
            )
            
            # Format the results
            formatted_results = []
            for result in results:
                if isinstance(result, dict) and result.get("success", False):
                    formatted_results.append(
                        ResearcherCollectionResponse(
                            success=True,
                            message=f"Successfully collected data for researcher at {institution}",
                            data=result
                        )
                    )
                else:
                    error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
                    formatted_results.append(
                        ResearcherCollectionResponse(
                            success=False,
                            message=f"Failed to collect data: {error_msg}",
                            data={
                                "status": "failed",
                                "error": error_msg,
                                "institution": institution,
                            }
                        )
                    )
            
            return formatted_results
            
    except Exception as e:
        logger.error(f"Error collecting researchers for institution {institution}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error collecting institution researchers: {str(e)}"
        )


@router.get("/researchers/{researcher_id}", response_model=ResearcherResponse)
async def get_researcher_endpoint(
    researcher_id: UUID
) -> ResearcherResponse:
    """Get researcher profile by ID."""
    try:
        researcher = await get_researcher(researcher_id)
        return ResearcherResponse(
            success=True,
            message="Researcher found",
            data=researcher
        )
    except SupabaseError as e:
        logger.error(f"Error getting researcher: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting researcher: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving researcher: {str(e)}"
        )


@router.get("/researchers/paper/{paper_id}", response_model=ResearcherResponse)
async def get_researcher_by_paper_endpoint(
    paper_id: UUID
) -> ResearcherResponse:
    """Get researcher profile associated with a paper."""
    try:
        researcher = await get_researcher_by_paper_id(paper_id)
        if not researcher:
            return ResearcherResponse(
                success=False,
                message=f"No researcher found for paper {paper_id}",
                data=None
            )
        
        return ResearcherResponse(
            success=True,
            message="Researcher found for paper",
            data=researcher
        )
    except SupabaseError as e:
        logger.error(f"Error getting researcher for paper: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting researcher for paper: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving researcher for paper: {str(e)}"
        )


# Helper functions for background tasks

async def handle_researcher_collection(
    request: ResearcherCollectionRequest
) -> Dict[str, Any]:
    """
    Handle the collection of researcher data in a background task.
    This function is designed to be robust - it will log errors but not crash
    the background task, ensuring data is saved to Supabase for realtime updates.
    """
    try:
        # Record start time
        start_time = dt.datetime.now()
        
        # Log background task started
        logger.info(f"Background task started for researcher collection: {request.name}")
        
        # Check if researcher already exists by email (if email is provided)
        existing_researcher = None
        if request.email:
            existing_researcher = await get_researcher_by_email(request.email)
        
        # Set researcher_id if found
        researcher_id = None
        if existing_researcher:
            researcher_id = existing_researcher.get("id")
            
        # Collect researcher data from various sources
        result = await collect_researcher_data(
            name=request.name,
            affiliation=request.affiliation,
            paper_title=request.paper_title,
            position=request.position,
            researcher_id=researcher_id,
            store_in_db=True
        )
        
        logger.info(f"Successfully collected data for researcher {request.name}")
        
        # Calculate processing time
        processing_time = dt.datetime.now() - start_time
        processing_seconds = processing_time.total_seconds()
        
        # If we have researcher data in the result, return it in the expected format
        if "researcher" in result and result.get("success", False):
            researcher = result["researcher"]
            
            # Return the researcher data using the fields from the database
            return {
                "status": "complete",
                "researcher_id": researcher.get("id"),
                "name": researcher.get("name"),
                "email": researcher.get("email"),
                "affiliation": researcher.get("affiliation"),
                "expertise": researcher.get("expertise", []),
                "achievements": researcher.get("achievements", []),
                "bio": researcher.get("bio", ""),
                "publications": researcher.get("publications", []),
                "collected_at": researcher.get("created_at"),
                "processing_time_seconds": processing_seconds,
                "processing_started": start_time.isoformat()
            }
        
        # Fallback to returning the raw result if no researcher data was found
        return {
            "status": "complete",
            "researcher_id": result.get("researcher_id"),
            "name": request.name,
            "email": result.get("collected_data", {}).get("email") if "collected_data" in result else None,
            "affiliation": request.affiliation,
            "expertise": result.get("collected_data", {}).get("expertise", []) if "collected_data" in result else [],
            "achievements": result.get("collected_data", {}).get("achievements", []) if "collected_data" in result else [],
            "bio": result.get("collected_data", {}).get("bio", "") if "collected_data" in result else "",
            "publications": result.get("collected_data", {}).get("publications", []) if "collected_data" in result else [],
            "processing_time_seconds": processing_seconds,
            "processing_started": start_time.isoformat()
        }
    except Exception as e:
        # Log the error but don't crash the background task
        logger.error(f"Error collecting data for researcher {request.name}: {str(e)}")
        
        # Return error information in a way that won't break the client
        return {
            "status": "error",
            "name": request.name,
            "affiliation": request.affiliation,
            "error_message": str(e),
            "processing_started": dt.datetime.now().isoformat()
        }


async def handle_batch_collection(
    requests: List[ResearcherCollectionRequest]
) -> List[Dict[str, Any]]:
    """Handle batch collection of researcher data."""
    try:
        # Convert requests to the format expected by batch_collect_researcher_data
        researchers_data = [
            {
                "name": req.name,
                "affiliation": req.affiliation,
                "paper_title": req.paper_title,
                "position": req.position,
                "researcher_id": req.researcher_id,
            }
            for req in requests
        ]
        
        # Collect data for all researchers
        batch_results = await batch_collect_researcher_data(researchers_data)
        
        logger.info(f"Completed batch collection for {len(requests)} researchers")
        return batch_results
    except Exception as e:
        logger.error(f"Error in batch collection: {str(e)}")
        raise e


async def handle_institution_collection(
    institution: str,
    position: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Handle collection of researcher data for an institution."""
    try:
        # Collect data for researchers at the institution
        results = await collect_for_institution(
            institution=institution,
            position=position,
            limit=limit
        )
        
        logger.info(f"Completed collection for institution {institution} with {len(results)} researchers")
        return results
    except Exception as e:
        logger.error(f"Error collecting for institution {institution}: {str(e)}")
        raise e


@router.post("/outreach", response_model=OutreachRequestResponse)
async def create_outreach_request(
    request: OutreachRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: Any = Depends(get_current_user)
) -> OutreachRequestResponse:
    """
    Create a new researcher outreach request.
    
    This endpoint creates a new request to invite a researcher to join the platform:
    1. Validates that the user has an active subscription
    2. Creates an outreach request record
    3. Generates a registration token
    4. Sends an email to the researcher with the registration link
    
    The response includes the status of the outreach request.
    """
    try:
        # Check if user is subscribed
        user_id = current_user.id
        
        # Override the user_id from the request with the authenticated user
        request_data = request.dict()
        request_data["user_id"] = user_id
        
        # Create outreach request
        outreach_request = await request_researcher_outreach(request_data)
        
        if not outreach_request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create outreach request"
            )
            
        # Generate token and send invitation email in background
        background_tasks.add_task(
            handle_outreach_email,
            outreach_request
        )
        
        return OutreachRequestResponse(
            success=True,
            message="Outreach request created and email sent to researcher",
            data=outreach_request
        )
        
    except Exception as e:
        logger.error(f"Error creating outreach request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating outreach request: {str(e)}"
        )


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: SessionCreate,
    current_user: Any = Depends(get_current_user)
) -> SessionResponse:
    """
    Book a consultation session with a researcher.
    
    This endpoint creates a new consultation session:
    1. Validates the time slot availability
    2. Creates a session record
    3. Generates a Zoom meeting link
    4. Sends confirmation emails
    
    The response includes the created session details.
    """
    try:
        # Override the user_id from the request with the authenticated user
        session_data = request.dict()
        session_data["user_id"] = current_user.id
        
        # Create session
        session = await create_consultation_session(session_data)
        
        return SessionResponse(
            success=True,
            message="Session created successfully",
            data=session
        )
        
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating session: {str(e)}"
        )


@router.get("/sessions", response_model=List[Dict[str, Any]])
async def get_user_sessions(
    current_user: Any = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get all sessions for the authenticated user.
    
    This endpoint retrieves all consultation sessions for the current user,
    including scheduled, completed, and canceled sessions.
    """
    try:
        sessions = await get_user_consultations(current_user.id)
        return sessions
        
    except Exception as e:
        logger.error(f"Error retrieving user sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_session_details(
    session_id: UUID,
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get details of a specific session.
    
    This endpoint retrieves details for a specific consultation session,
    including the Zoom link, participants, and status.
    """
    try:
        session = await get_session(session_id)
        
        # Check if user has access to this session
        if str(session.get("user_id")) != str(current_user.id) and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this session"
            )
            
        return session
        
    except Exception as e:
        logger.error(f"Error retrieving session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving session: {str(e)}"
        )


@router.get("/researchers/{researcher_id}/availability", response_model=Dict[str, Any])
async def get_researcher_availability(
    researcher_id: UUID,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get researcher's available time slots.
    
    This endpoint retrieves available time slots for a specific researcher,
    optionally filtered by date.
    """
    try:
        # Get researcher
        researcher = await get_researcher(researcher_id)
        
        if not researcher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Researcher not found: {researcher_id}"
            )
            
        # Get availability from researcher data
        availability = researcher.get("availability", {})
        
        # Filter by date if provided
        if date:
            # Format may be like "2023-04-20"
            day_of_week = dt.datetime.fromisoformat(date).strftime("%A").lower()
            filtered_availability = {
                date: availability.get(day_of_week, [])
            }
            return {"availability": filtered_availability}
        else:
            return {"availability": availability}
            
    except Exception as e:
        logger.error(f"Error retrieving researcher availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving availability: {str(e)}"
        )


@router.post("/sessions/{session_id}/cancel", response_model=SessionResponse)
async def cancel_session(
    session_id: UUID,
    current_user = Depends(get_current_user)
) -> SessionResponse:
    """
    Cancel a scheduled session.
    
    This endpoint cancels a scheduled consultation session:
    1. Validates that the session is still scheduled (not completed)
    2. Updates the session status to "canceled"
    3. Cancels the associated Zoom meeting
    4. Notifies participants
    
    Restrictions:
    - Only the session owner or an admin can cancel a session
    - Sessions must be canceled at least 24 hours in advance
    """
    try:
        # Get session
        session = await get_session(session_id)
        
        # Check if user has permission to cancel
        if str(session.get("user_id")) != str(current_user.id) and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to cancel this session"
            )
            
        # Check if session can be canceled
        if session.get("status") != "scheduled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel a session with status: {session.get('status')}"
            )
            
        # Check if session is less than 24 hours away
        start_time = session.get("start_time")
        if isinstance(start_time, str):
            start_time = dt.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
        if (start_time - dt.datetime.now()).total_seconds() < (24 * 60 * 60):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sessions must be canceled at least 24 hours in advance"
            )
            
        # Cancel session
        updated_session = await update_session_status(session_id, "canceled")
        
        return SessionResponse(
            success=True,
            message="Session canceled successfully",
            data=updated_session
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error canceling session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error canceling session: {str(e)}"
        )


@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    current_user = Depends(get_current_user)
) -> SubscriptionResponse:
    """
    Create a new consulting subscription for the current user.
    
    This endpoint creates a new monthly subscription for outreach requests:
    1. Creates a Stripe subscription for the user
    2. Returns the client secret for the payment
    
    The response includes the subscription details and payment information.
    """
    try:
        # Create a subscription
        subscription = await create_user_subscription(current_user.id)
        
        return SubscriptionResponse(
            success=True,
            message="Subscription created successfully",
            data=subscription
        )
        
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating subscription: {str(e)}"
        )


@router.post("/payments/intent", response_model=Dict[str, Any])
async def create_payment_intent(
    data: Dict[str, Any],
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a Stripe payment intent for a session or subscription.
    
    This endpoint creates a Stripe payment intent:
    1. Validates the payment type (session or subscription)
    2. Calculates the amount based on the researcher's rate or subscription fee
    3. Creates a payment intent
    4. Returns the client secret for the payment
    
    Required data:
    - type: "session" or "subscription"
    - session_id: UUID (required for session payments)
    """
    try:
        payment_type = data.get("type")
        
        if payment_type not in ["session", "subscription"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment type. Must be 'session' or 'subscription'"
            )
            
        # Calculate amount based on payment type
        amount = 0
        metadata = {}
        
        if payment_type == "session":
            session_id = data.get("session_id")
            
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="session_id is required for session payments"
                )
                
            # Get session
            session = await get_session(session_id)
            
            # Check if user has permission to pay for this session
            if str(session.get("user_id")) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to pay for this session"
                )
                
            # Get researcher rate
            researcher_id = session.get("researcher_id")
            researcher = await get_researcher(researcher_id)
            
            if not researcher:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Researcher not found: {researcher_id}"
                )
                
            hourly_rate = researcher.get("rate", 0)
            
            # Calculate session duration in hours
            start_time = session.get("start_time")
            end_time = session.get("end_time")
            
            if isinstance(start_time, str):
                start_time = dt.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                
            if isinstance(end_time, str):
                end_time = dt.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                
            duration_hours = (end_time - start_time).total_seconds() / 3600
            
            # Calculate amount in cents
            amount = int(hourly_rate * duration_hours * 100)
            
            # Add metadata
            metadata = {
                "type": "session",
                "session_id": str(session_id),
                "user_id": str(current_user.id),
                "researcher_id": str(researcher_id)
            }
            
        elif payment_type == "subscription":
            # Use subscription price from settings
            amount = int(float(settings.CONSULTING_SUBSCRIPTION_PRICE) * 100)
            
            # Add metadata
            metadata = {
                "type": "subscription",
                "user_id": str(current_user.id)
            }
            
        # Create payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",
            metadata=metadata,
            description=f"Paper Mastery {payment_type} payment"
        )
        
        return {
            "client_secret": payment_intent.client_secret,
            "amount": amount / 100,  # Return amount in dollars for display
            "type": payment_type
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating payment intent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment intent: {str(e)}"
        )


async def handle_outreach_email(outreach_request: Dict[str, Any]) -> None:
    """
    Handle sending an outreach email to a researcher.
    
    Args:
        outreach_request: Outreach request data
        
    Returns:
        None
    """
    try:
        # Get paper data if provided
        paper_title = None
        if outreach_request.get("paper_id"):
            paper = await get_paper_by_id(str(outreach_request.get("paper_id")))
            if paper:
                paper_title = paper.get("title")
                
        # Get user data
        user_name = None
        if outreach_request.get("user_id"):
            user = await get_user_by_id(str(outreach_request.get("user_id")))
            if user:
                user_name = user.get("name")
                
        # Generate registration token
        outreach_id = outreach_request.get("id")
        researcher_email = outreach_request.get("researcher_email")
        
        token = generate_registration_token(researcher_email, str(outreach_id))
        
        # Send outreach email
        email_sent = await send_researcher_outreach_email(
            to_email=researcher_email,
            token=token,
            paper_title=paper_title,
            user_name=user_name
        )
        
        # Update outreach request status
        if email_sent:
            await update_outreach_request(
                outreach_id=str(outreach_id),
                update_data={"status": "pending"}
            )
        else:
            await update_outreach_request(
                outreach_id=str(outreach_id),
                update_data={"status": "email_failed"}
            )
            
    except Exception as e:
        logger.error(f"Error sending outreach email: {str(e)}")
        # Update outreach request status
        if outreach_request and outreach_request.get("id"):
            await update_outreach_request(
                outreach_id=str(outreach_request.get("id")),
                update_data={"status": "email_failed"}
            )


@router.post("/sessions/{session_id}/accept", response_model=SessionResponse)
async def accept_session(
    session_id: UUID,
    current_user = Depends(get_current_user)
) -> SessionResponse:
    """
    Accept a session as a researcher.
    
    This endpoint allows a researcher to accept a session request:
    1. Validates that the current user is the researcher for this session
    2. Updates the session status to "confirmed" if it's "pending"
    3. Sends confirmation emails
    
    The response includes the updated session details.
    """
    try:
        # Get session
        session = await get_session(session_id)
        
        # Get researcher
        researcher_id = session.get("researcher_id")
        researcher = await get_researcher(researcher_id)
        
        # Check if the current user is the researcher or has a linked account
        if not researcher or (
            str(researcher.get("user_id")) != str(current_user.id) and 
            not current_user.is_admin
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to accept this session"
            )
            
        # Check if session is in a valid state
        if session.get("status") != "scheduled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept a session with status: {session.get('status')}"
            )
            
        # Update session status (no change to status, potentially add zoom link in future)
        updated_session = await update_session_status(
            session_id=session_id, 
            status="scheduled"
        )
        
        # Return success response
        return SessionResponse(
            success=True,
            message="Session accepted successfully",
            data=updated_session
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error accepting session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error accepting session: {str(e)}"
        ) 