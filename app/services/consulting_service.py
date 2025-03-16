from typing import Dict, Any, List, Optional, Union
from uuid import UUID
import datetime
import httpx
import json

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError, SupabaseError
from app.database.supabase_client import (
    get_researcher_by_id,
    get_researcher_by_email,
    create_researcher,
    update_researcher,
    create_outreach_request,
    update_outreach_request,
    get_outreach_request_by_id,
    create_session,
    update_session,
    get_session_by_id,
    create_payment,
    create_subscription,
    get_sessions_by_researcher,
    get_sessions_by_user
)
from app.services.email_service import send_email

logger = get_logger(__name__)
settings = get_settings()

class ConsultingError(ExternalAPIError):
    """Exception raised for errors in the consulting service."""
    pass


async def get_researcher(researcher_id: UUID) -> Dict[str, Any]:
    """
    Get researcher by ID.
    
    Args:
        researcher_id: UUID of the researcher
        
    Returns:
        Dictionary containing researcher information
        
    Raises:
        ConsultingError: If there's an error retrieving the researcher
    """
    try:
        researcher = await get_researcher_by_id(str(researcher_id))
        if not researcher:
            logger.warning(f"Researcher with ID {researcher_id} not found")
            raise ConsultingError(f"Researcher with ID {researcher_id} not found")
        
        return researcher
    except SupabaseError as e:
        logger.error(f"Database error retrieving researcher {researcher_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving researcher: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving researcher {researcher_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving researcher: {str(e)}")


async def get_researcher_by_paper_id(paper_id: UUID) -> Dict[str, Any]:
    """
    Get researcher associated with a paper ID.
    
    Args:
        paper_id: UUID of the paper
        
    Returns:
        Dictionary containing researcher information
        
    Raises:
        ConsultingError: If there's an error retrieving the researcher or no researcher is associated with the paper
    """
    try:
        # Get paper from database to find primary_researcher_id
        from app.database.supabase_client import get_paper_by_id
        
        paper = await get_paper_by_id(str(paper_id))
        if not paper:
            logger.warning(f"Paper with ID {paper_id} not found")
            raise ConsultingError(f"Paper with ID {paper_id} not found")
            
        researcher_id = paper.get("primary_researcher_id")
        if not researcher_id:
            logger.warning(f"No primary researcher associated with paper {paper_id}")
            raise ConsultingError(f"No primary researcher associated with paper {paper_id}")
            
        researcher = await get_researcher_by_id(researcher_id)
        if not researcher:
            logger.warning(f"Researcher with ID {researcher_id} not found for paper {paper_id}")
            raise ConsultingError(f"Researcher associated with paper {paper_id} not found")
        
        return researcher
    except SupabaseError as e:
        logger.error(f"Database error retrieving researcher for paper {paper_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving researcher for paper: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving researcher for paper {paper_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving researcher for paper: {str(e)}")


async def create_or_update_researcher_profile(
    researcher_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create or update a researcher profile.
    
    Args:
        researcher_data: Dictionary containing researcher information
        
    Returns:
        Dictionary containing the created or updated researcher
        
    Raises:
        ConsultingError: If there's an error creating or updating the researcher
    """
    try:
        # Check if researcher exists by email
        email = researcher_data.get("email")
        if not email:
            logger.error("Email is required for researcher profile")
            raise ConsultingError("Email is required for researcher profile")
            
        existing_researcher = await get_researcher_by_email(email)
        
        if existing_researcher:
            # Update existing researcher
            researcher_id = existing_researcher.get("id")
            updated_researcher = await update_researcher(researcher_id, researcher_data)
            logger.info(f"Updated researcher profile for {email}")
            return updated_researcher
        else:
            # Create new researcher
            new_researcher = await create_researcher(researcher_data)
            logger.info(f"Created new researcher profile for {email}")
            return new_researcher
    except SupabaseError as e:
        logger.error(f"Database error creating/updating researcher: {str(e)}")
        raise ConsultingError(f"Error creating/updating researcher: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating/updating researcher: {str(e)}")
        raise ConsultingError(f"Error creating/updating researcher: {str(e)}")


async def request_researcher_outreach(
    request_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Request outreach to a researcher.
    
    Args:
        request_data: Dictionary containing:
            - user_id: ID of the requesting user
            - researcher_email: Email of the researcher
            - paper_id: Optional paper ID
            
    Returns:
        Dictionary containing the created outreach request
        
    Raises:
        ConsultingError: If there's an error creating the outreach request
    """
    try:
        # Create outreach request in database
        outreach_request = await create_outreach_request(request_data)
        
        # Send email to researcher
        user_id = request_data.get("user_id")
        researcher_email = request_data.get("researcher_email")
        paper_id = request_data.get("paper_id")
        
        # Get user details
        user = await get_user(str(user_id))
        
        if not user:
            logger.warning(f"User with ID {user_id} not found for outreach request")
            # Continue with the process - we already created the request
        
        # Get paper details if provided
        paper_title = None
        if paper_id:
            from app.database.supabase_client import get_paper_by_id
            paper = await get_paper_by_id(paper_id)
            if paper:
                paper_title = paper.get("title")
        
        # Prepare email content
        user_name = user.get("full_name") if user else "A PaperMastery user"
        subject = f"Consultation Request from {user_name} via PaperMastery"
        
        content = f"""
        Hello,
        
        {user_name} has requested a consultation with you through the PaperMastery platform.
        """
        
        if paper_title:
            content += f"\n\nThe consultation is regarding the paper: {paper_title}"
            
        content += """
        
        If you're interested in providing expert consultation, please reply to this email
        or visit [PaperMastery Consulting](https://papermastery.ai/consulting) to set up your profile.
        
        Best regards,
        The PaperMastery Team
        """
        
        # Send the email
        try:
            await send_email(
                to_email=researcher_email,
                subject=subject,
                content=content
            )
            
            # Update outreach request status
            await update_outreach_request(
                outreach_request.get("id"),
                {"status": "email_sent"}
            )
            
            logger.info(f"Sent outreach email to {researcher_email}")
        except Exception as e:
            logger.error(f"Error sending outreach email to {researcher_email}: {str(e)}")
            # Update outreach request status
            await update_outreach_request(
                outreach_request.get("id"),
                {"status": "email_failed"}
            )
        
        return outreach_request
    except SupabaseError as e:
        logger.error(f"Database error creating outreach request: {str(e)}")
        raise ConsultingError(f"Error creating outreach request: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating outreach request: {str(e)}")
        raise ConsultingError(f"Error creating outreach request: {str(e)}")


async def handle_researcher_response(
    outreach_id: UUID,
    response: str
) -> Dict[str, Any]:
    """
    Handle researcher response to outreach request.
    
    Args:
        outreach_id: ID of the outreach request
        response: Response from the researcher ('accept' or 'decline')
        
    Returns:
        Dictionary containing the updated outreach request
        
    Raises:
        ConsultingError: If there's an error updating the outreach request
    """
    try:
        # Get the outreach request
        outreach_request = await get_outreach_request_by_id(str(outreach_id))
        if not outreach_request:
            logger.warning(f"Outreach request with ID {outreach_id} not found")
            raise ConsultingError(f"Outreach request with ID {outreach_id} not found")
        
        # Validate response
        if response not in ['accept', 'decline']:
            logger.error(f"Invalid response '{response}' for outreach request")
            raise ConsultingError(f"Invalid response: must be 'accept' or 'decline'")
            
        # Update outreach request status
        status = "accepted" if response == "accept" else "declined"
        updated_request = await update_outreach_request(
            str(outreach_id),
            {"status": status}
        )
        
        # If accepted, notify the user
        if response == "accept":
            user_id = outreach_request.get("user_id")
            researcher_email = outreach_request.get("researcher_email")
            
            # Get user details
            user = await get_user(str(user_id))
            
            if user and user.get("email"):
                # Get researcher details
                researcher = await get_researcher_by_email(researcher_email)
                researcher_name = researcher.get("name") if researcher else "The researcher"
                
                # Prepare email content
                subject = f"Consultation Request Accepted by {researcher_name}"
                
                content = f"""
                Hello {user.get('full_name', 'there')},
                
                Good news! {researcher_name} has accepted your consultation request.
                
                You can now book a session at [PaperMastery Consulting](https://papermastery.ai/consulting/book).
                
                Best regards,
                The PaperMastery Team
                """
                
                # Send the email
                try:
                    await send_email(
                        to_email=user.get("email"),
                        subject=subject,
                        content=content
                    )
                    logger.info(f"Sent acceptance notification to user {user_id}")
                except Exception as e:
                    logger.error(f"Error sending acceptance notification to user {user_id}: {str(e)}")
        
        return updated_request
    except SupabaseError as e:
        logger.error(f"Database error updating outreach request {outreach_id}: {str(e)}")
        raise ConsultingError(f"Error updating outreach request: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error updating outreach request {outreach_id}: {str(e)}")
        raise ConsultingError(f"Error updating outreach request: {str(e)}")


async def book_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Book a consultation session.
    
    Args:
        session_data: Dictionary containing session details
            - user_id: ID of the user booking the session
            - researcher_id: ID of the researcher
            - paper_id: Optional paper ID
            - start_time: Start time of the session
            - end_time: End time of the session
            
    Returns:
        Dictionary containing the created session
        
    Raises:
        ConsultingError: If there's an error creating the session
    """
    try:
        # Generate Zoom meeting link
        try:
            zoom_link = await create_zoom_meeting(
                topic=f"PaperMastery Consultation",
                start_time=session_data.get("start_time"),
                duration_minutes=int((session_data.get("end_time") - session_data.get("start_time")).total_seconds() / 60)
            )
            session_data["zoom_link"] = zoom_link
        except Exception as e:
            logger.error(f"Error creating Zoom meeting: {str(e)}")
            # Continue without Zoom link
        
        # Create session in database
        session = await create_session(session_data)
        
        # Create payment record if needed
        # For now, we'll assume payment is handled separately
        
        # Notify the user and researcher via email
        user_id = session_data.get("user_id")
        researcher_id = session_data.get("researcher_id")
        
        # Get user details
        user = await get_user(str(user_id))
        
        # Get researcher details
        researcher = await get_researcher_by_id(researcher_id)
        
        if user and user.get("email") and researcher and researcher.get("email"):
            # Format session time for display
            start_time = session_data.get("start_time")
            end_time = session_data.get("end_time")
            
            formatted_start = start_time.strftime("%A, %B %d, %Y at %I:%M %p")
            formatted_duration = f"{int((end_time - start_time).total_seconds() / 60)} minutes"
            
            # Email to user
            user_subject = f"Your consultation with {researcher.get('name')} is confirmed"
            user_content = f"""
            Hello {user.get('full_name', 'there')},
            
            Your consultation session with {researcher.get('name')} has been confirmed.
            
            Session details:
            - Date and time: {formatted_start}
            - Duration: {formatted_duration}
            """
            
            if session_data.get("zoom_link"):
                user_content += f"\n- Zoom link: {session_data.get('zoom_link')}"
                
            user_content += """
            
            If you need to reschedule or cancel, please do so at least 24 hours in advance.
            
            Best regards,
            The PaperMastery Team
            """
            
            # Email to researcher
            researcher_subject = f"New consultation session with {user.get('full_name')}"
            researcher_content = f"""
            Hello {researcher.get('name')},
            
            A new consultation session has been booked with you by {user.get('full_name')}.
            
            Session details:
            - Date and time: {formatted_start}
            - Duration: {formatted_duration}
            """
            
            if session_data.get("zoom_link"):
                researcher_content += f"\n- Zoom link: {session_data.get('zoom_link')}"
                
            researcher_content += """
            
            Please ensure you're available at the scheduled time.
            
            Best regards,
            The PaperMastery Team
            """
            
            # Send the emails
            try:
                await send_email(
                    to_email=user.get("email"),
                    subject=user_subject,
                    content=user_content
                )
                logger.info(f"Sent session confirmation to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending session confirmation to user {user_id}: {str(e)}")
                
            try:
                await send_email(
                    to_email=researcher.get("email"),
                    subject=researcher_subject,
                    content=researcher_content
                )
                logger.info(f"Sent session notification to researcher {researcher_id}")
            except Exception as e:
                logger.error(f"Error sending session notification to researcher {researcher_id}: {str(e)}")
        
        # If there's a paper_id, update the Paper and Progress models
        paper_id = session_data.get("paper_id")
        if paper_id:
            try:
                # Update paper to mark consulting as available
                updated_paper = await update_paper(str(paper_id), {
                    "has_consulting_available": True,
                    "primary_researcher_id": researcher_id
                })
                
                # Update progress to mark consulted
                updated_progress = await update_progress(str(user_id), str(paper_id), {
                    "has_consulted": True,
                    "last_consulting_session": session_data.get("start_time")
                })
                
                logger.info(f"Updated paper {paper_id} and progress for consulting")
            except Exception as e:
                logger.error(f"Error updating paper and progress for consulting: {str(e)}")
        
        return session
    except SupabaseError as e:
        logger.error(f"Database error creating session: {str(e)}")
        raise ConsultingError(f"Error creating session: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating session: {str(e)}")
        raise ConsultingError(f"Error creating session: {str(e)}")


async def update_session_status(
    session_id: UUID,
    status: str
) -> Dict[str, Any]:
    """
    Update the status of a consultation session.
    
    Args:
        session_id: ID of the session
        status: New status ('scheduled', 'completed', 'canceled')
        
    Returns:
        Dictionary containing the updated session
        
    Raises:
        ConsultingError: If there's an error updating the session
    """
    try:
        # Validate status
        valid_statuses = ['scheduled', 'completed', 'canceled']
        if status not in valid_statuses:
            logger.error(f"Invalid session status '{status}'")
            raise ConsultingError(f"Invalid status: must be one of {valid_statuses}")
            
        # Update session in database
        updated_session = await update_session(
            str(session_id),
            {"status": status}
        )
        
        # Get session details for notifications
        session = await get_session_by_id(str(session_id))
        if not session:
            logger.warning(f"Session with ID {session_id} not found after update")
            return updated_session
        
        # Notify participants if session is completed or canceled
        if status in ['completed', 'canceled']:
            user_id = session.get("user_id")
            researcher_id = session.get("researcher_id")
            
            # Get user details
            user = await get_user(str(user_id))
            
            # Get researcher details
            researcher = await get_researcher_by_id(researcher_id)
            
            if user and user.get("email") and researcher and researcher.get("email"):
                status_text = "completed" if status == "completed" else "canceled"
                
                # Email to user
                user_subject = f"Your consultation session has been {status_text}"
                user_content = f"""
                Hello {user.get('full_name', 'there')},
                
                Your consultation session with {researcher.get('name')} has been {status_text}.
                """
                
                if status == "completed":
                    user_content += """
                    
                    We hope you found the session valuable. If you'd like to provide feedback
                    or book another session, please visit [PaperMastery Consulting](https://papermastery.ai/consulting).
                    """
                
                user_content += """
                
                Best regards,
                The PaperMastery Team
                """
                
                # Send the email
                try:
                    await send_email(
                        to_email=user.get("email"),
                        subject=user_subject,
                        content=user_content
                    )
                    logger.info(f"Sent session {status} notification to user {user_id}")
                except Exception as e:
                    logger.error(f"Error sending session {status} notification to user {user_id}: {str(e)}")
        
        return updated_session
    except SupabaseError as e:
        logger.error(f"Database error updating session {session_id}: {str(e)}")
        raise ConsultingError(f"Error updating session: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error updating session {session_id}: {str(e)}")
        raise ConsultingError(f"Error updating session: {str(e)}")


async def get_researcher_sessions(researcher_id: UUID) -> List[Dict[str, Any]]:
    """
    Get all sessions for a researcher.
    
    Args:
        researcher_id: ID of the researcher
        
    Returns:
        List of session dictionaries
        
    Raises:
        ConsultingError: If there's an error retrieving the sessions
    """
    try:
        sessions = await get_sessions_by_researcher(researcher_id)
        return sessions
    except SupabaseError as e:
        logger.error(f"Database error retrieving sessions for researcher {researcher_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving sessions: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving sessions for researcher {researcher_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving sessions: {str(e)}")


async def get_user_sessions(user_id: UUID) -> List[Dict[str, Any]]:
    """
    Get all sessions for a user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        List of session dictionaries
        
    Raises:
        ConsultingError: If there's an error retrieving the sessions
    """
    try:
        sessions = await get_sessions_by_user(str(user_id))
        return sessions
    except SupabaseError as e:
        logger.error(f"Database error retrieving sessions for user {user_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving sessions: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving sessions for user {user_id}: {str(e)}")
        raise ConsultingError(f"Error retrieving sessions: {str(e)}")


async def create_user_subscription(user_id: UUID) -> Dict[str, Any]:
    """
    Create a subscription for a user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        Dictionary containing the created subscription
        
    Raises:
        ConsultingError: If there's an error creating the subscription
    """
    try:
        # Create subscription in database
        subscription = await create_subscription({
            "user_id": str(user_id),
            "status": "active",
            "start_date": datetime.datetime.now(),
            "end_date": datetime.datetime.now() + datetime.timedelta(days=30),
            "price": settings.CONSULTING_SUBSCRIPTION_PRICE
        })
        
        # Get user details for notification
        user = await get_user(str(user_id))
        
        if user and user.get("email"):
            # Prepare email content
            subject = "Your PaperMastery Consulting Subscription is Active"
            
            content = f"""
            Hello {user.get('full_name', 'there')},
            
            Thank you for subscribing to PaperMastery Consulting!
            
            Your subscription is now active and will renew automatically on {subscription.get('end_date').strftime('%B %d, %Y')}.
            
            With your subscription, you can:
            - Request consultations with researchers
            - Book sessions with top experts in your field
            - Get personalized guidance on your research
            
            Visit [PaperMastery Consulting](https://papermastery.ai/consulting) to start exploring.
            
            Best regards,
            The PaperMastery Team
            """
            
            # Send the email
            try:
                await send_email(
                    to_email=user.get("email"),
                    subject=subject,
                    content=content
                )
                logger.info(f"Sent subscription confirmation to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending subscription confirmation to user {user_id}: {str(e)}")
        
        return subscription
    except SupabaseError as e:
        logger.error(f"Database error creating subscription for user {user_id}: {str(e)}")
        raise ConsultingError(f"Error creating subscription: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating subscription for user {user_id}: {str(e)}")
        raise ConsultingError(f"Error creating subscription: {str(e)}")


# Helper function for Zoom meetings
async def create_zoom_meeting(
    topic: str,
    start_time: datetime.datetime,
    duration_minutes: int = 60
) -> str:
    """
    Create a Zoom meeting and return the meeting URL.
    
    Args:
        topic: Meeting topic
        start_time: Meeting start time
        duration_minutes: Meeting duration in minutes
        
    Returns:
        Zoom meeting URL
        
    Raises:
        ConsultingError: If there's an error creating the Zoom meeting
    """
    try:
        api_key = settings.ZOOM_API_KEY
        api_secret = settings.ZOOM_API_SECRET
        
        if not api_key or not api_secret:
            logger.error("Zoom API credentials are not configured")
            return None
            
        # Generate JWT token for authentication
        import jwt
        import time
        
        token_exp = int(time.time()) + 3600  # 1 hour expiration
        
        payload = {
            "iss": api_key,
            "exp": token_exp
        }
        
        jwt_token = jwt.encode(payload, api_secret, algorithm="HS256")
        
        # Format start time for Zoom
        formatted_start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Create Zoom meeting
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.zoom.us/v2/users/me/meetings",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "topic": topic,
                    "type": 2,  # Scheduled meeting
                    "start_time": formatted_start_time,
                    "duration": duration_minutes,
                    "timezone": "UTC",
                    "settings": {
                        "host_video": True,
                        "participant_video": True,
                        "join_before_host": True,
                        "waiting_room": False
                    }
                }
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Zoom API error: {response.status_code} {response.text}")
                return None
                
            meeting_data = response.json()
            meeting_url = meeting_data.get("join_url")
            
            logger.info(f"Created Zoom meeting: {meeting_url}")
            return meeting_url
                
    except Exception as e:
        logger.error(f"Error creating Zoom meeting: {str(e)}")
        return None


async def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Stub function to get user details. This needs to be implemented.
    
    Args:
        user_id: ID of the user
        
    Returns:
        User details or None if not found
    """
    logger.warning(f"get_user not implemented yet, returning dummy user for {user_id}")
    # Return a minimal dummy user for now
    return {
        "id": user_id,
        "email": "user@example.com",
        "full_name": "Test User"
    }

async def update_progress(user_id: str, paper_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stub function to update user progress. This needs to be implemented.
    
    Args:
        user_id: ID of the user
        paper_id: ID of the paper
        update_data: Data to update
        
    Returns:
        Updated progress data
    """
    logger.warning(f"update_progress not implemented yet, returning dummy update for user {user_id} and paper {paper_id}")
    return {
        "user_id": user_id,
        "paper_id": paper_id,
        "has_consulted": update_data.get("has_consulted", False),
        "last_consulting_session": update_data.get("last_consulting_session")
    }

async def update_paper(paper_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stub function to update paper. This needs to be implemented.
    
    Args:
        paper_id: ID of the paper
        update_data: Data to update
        
    Returns:
        Updated paper data
    """
    logger.warning(f"update_paper not implemented yet in this context, returning dummy update for paper {paper_id}")
    return {
        "id": paper_id,
        **update_data
    } 