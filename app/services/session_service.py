from typing import Dict, Any, List, Optional, Union
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import asyncio

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.exceptions import ServiceError
from app.database.supabase_client import (
    create_session,
    update_session,
    get_session_by_id,
    get_sessions_by_researcher,
    get_sessions_by_user,
    get_researcher_by_id,
    get_user_by_id,
    get_paper_by_id
)
from app.services.zoom_service import create_zoom_meeting, update_meeting, delete_meeting
from app.services.email_service import (
    send_session_confirmation_email,
    send_session_reminder_email
)

logger = get_logger(__name__)
settings = get_settings()

class SessionError(ServiceError):
    """Exception raised for errors in the session service."""
    pass


async def create_consultation_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new consultation session.
    
    Args:
        session_data: Dictionary containing session data
            Required fields:
            - user_id: UUID of the user
            - researcher_id: UUID of the researcher
            - start_time: Start time of the session
            - end_time: End time of the session
            Optional fields:
            - paper_id: UUID of the paper (if applicable)
            - status: Status of the session (defaults to "scheduled")
    
    Returns:
        Dictionary containing the created session
        
    Raises:
        SessionError: If there's an error creating the session
    """
    try:
        # Validate required fields
        required_fields = ["user_id", "researcher_id", "start_time", "end_time"]
        for field in required_fields:
            if field not in session_data:
                raise SessionError(f"Missing required field: {field}")
                
        # Validate start and end times
        start_time = session_data["start_time"]
        end_time = session_data["end_time"]
        
        # Convert string times to datetime if needed
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            session_data["start_time"] = start_time
            
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            session_data["end_time"] = end_time
            
        # Ensure start_time is in the future
        if start_time < datetime.now():
            raise SessionError("Session start time must be in the future")
            
        # Ensure end_time is after start_time
        if end_time <= start_time:
            raise SessionError("Session end time must be after start time")
            
        # Check if researcher exists
        researcher_id = session_data["researcher_id"]
        researcher = await get_researcher_by_id(str(researcher_id))
        
        if not researcher:
            raise SessionError(f"Researcher not found: {researcher_id}")
            
        # Check if paper exists if paper_id is provided
        if "paper_id" in session_data and session_data["paper_id"]:
            paper_id = session_data["paper_id"]
            paper = await get_paper_by_id(str(paper_id))
            
            if not paper:
                raise SessionError(f"Paper not found: {paper_id}")
                
        # Set default status if not provided
        if "status" not in session_data:
            session_data["status"] = "scheduled"
            
        # Create session in database
        session = await create_session(session_data)
        
        if not session:
            raise SessionError("Failed to create session")
            
        # Create Zoom meeting for the session
        try:
            user = await get_user_by_id(str(session_data["user_id"]))
            user_name = user.get("name", "User")
            
            # Determine meeting topic
            if "paper_id" in session_data and session_data["paper_id"]:
                paper = await get_paper_by_id(str(session_data["paper_id"]))
                paper_title = paper.get("title", "Paper consultation")
                topic = f"Paper Mastery: Consultation on {paper_title}"
            else:
                topic = f"Paper Mastery: Consultation with {researcher.get('name', 'Researcher')}"
                
            # Create Zoom meeting
            meeting = await create_zoom_meeting(
                topic=topic,
                start_time=start_time,
                duration_minutes=int((end_time - start_time).total_seconds() / 60),
                agenda=f"Consultation session between {user_name} and {researcher.get('name', 'Researcher')}"
            )
            
            # Update session with Zoom link
            zoom_link = meeting.get("join_url")
            if zoom_link:
                session = await update_session(
                    session_id=session["id"],
                    update_data={"zoom_link": zoom_link}
                )
                
        except Exception as e:
            logger.error(f"Error creating Zoom meeting: {str(e)}")
            # Continue without Zoom link if meeting creation fails
            
        # Send confirmation emails (in background)
        asyncio.create_task(send_session_notifications(session))
            
        return session
        
    except SessionError as e:
        # Re-raise session-specific errors
        raise
    except Exception as e:
        logger.error(f"Error creating consultation session: {str(e)}")
        raise SessionError(f"Error creating consultation session: {str(e)}")


async def get_session(session_id: Union[str, UUID]) -> Dict[str, Any]:
    """
    Get a session by ID.
    
    Args:
        session_id: UUID of the session
        
    Returns:
        Dictionary containing the session data
        
    Raises:
        SessionError: If there's an error retrieving the session
    """
    try:
        session = await get_session_by_id(str(session_id))
        
        if not session:
            raise SessionError(f"Session not found: {session_id}")
            
        return session
        
    except Exception as e:
        logger.error(f"Error retrieving session: {str(e)}")
        raise SessionError(f"Error retrieving session: {str(e)}")


async def update_session_status(
    session_id: Union[str, UUID],
    status: str,
    zoom_link: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update a session's status.
    
    Args:
        session_id: UUID of the session
        status: New status ("scheduled", "completed", "canceled")
        zoom_link: Optional new Zoom link
        
    Returns:
        Dictionary containing the updated session
        
    Raises:
        SessionError: If there's an error updating the session
    """
    try:
        # Validate status
        valid_statuses = ["scheduled", "completed", "canceled"]
        if status not in valid_statuses:
            raise SessionError(f"Invalid status: {status}. Must be one of {valid_statuses}")
            
        # Get current session
        session = await get_session_by_id(str(session_id))
        
        if not session:
            raise SessionError(f"Session not found: {session_id}")
            
        # Prepare update data
        update_data = {"status": status}
        
        if zoom_link:
            update_data["zoom_link"] = zoom_link
            
        # Update session
        updated_session = await update_session(
            session_id=str(session_id),
            update_data=update_data
        )
        
        if not updated_session:
            raise SessionError(f"Failed to update session: {session_id}")
            
        # If status is canceled, try to delete the Zoom meeting
        if status == "canceled" and session.get("zoom_link"):
            try:
                # Extract meeting ID from zoom link
                # Format: https://zoom.us/j/1234567890?pwd=abcdef
                zoom_link = session["zoom_link"]
                meeting_id = zoom_link.split("/j/")[1].split("?")[0]
                
                # Delete Zoom meeting
                await delete_meeting(meeting_id)
                
            except Exception as e:
                logger.error(f"Error deleting Zoom meeting: {str(e)}")
                # Continue even if Zoom meeting deletion fails
        
        return updated_session
        
    except SessionError as e:
        # Re-raise session-specific errors
        raise
    except Exception as e:
        logger.error(f"Error updating session status: {str(e)}")
        raise SessionError(f"Error updating session status: {str(e)}")


async def get_researcher_consultations(researcher_id: Union[str, UUID]) -> List[Dict[str, Any]]:
    """
    Get all sessions for a researcher.
    
    Args:
        researcher_id: UUID of the researcher
        
    Returns:
        List of session dictionaries
        
    Raises:
        SessionError: If there's an error retrieving the sessions
    """
    try:
        sessions = await get_sessions_by_researcher(str(researcher_id))
        return sessions
        
    except Exception as e:
        logger.error(f"Error retrieving researcher sessions: {str(e)}")
        raise SessionError(f"Error retrieving researcher sessions: {str(e)}")


async def get_user_consultations(user_id: Union[str, UUID]) -> List[Dict[str, Any]]:
    """
    Get all sessions for a user.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        List of session dictionaries
        
    Raises:
        SessionError: If there's an error retrieving the sessions
    """
    try:
        sessions = await get_sessions_by_user(str(user_id))
        return sessions
        
    except Exception as e:
        logger.error(f"Error retrieving user sessions: {str(e)}")
        raise SessionError(f"Error retrieving user sessions: {str(e)}")


async def reschedule_session(
    session_id: Union[str, UUID],
    start_time: datetime,
    end_time: datetime
) -> Dict[str, Any]:
    """
    Reschedule a session.
    
    Args:
        session_id: UUID of the session
        start_time: New start time
        end_time: New end time
        
    Returns:
        Dictionary containing the updated session
        
    Raises:
        SessionError: If there's an error rescheduling the session
    """
    try:
        # Validate times
        if end_time <= start_time:
            raise SessionError("End time must be after start time")
            
        if start_time < datetime.now():
            raise SessionError("Start time must be in the future")
            
        # Get current session
        session = await get_session_by_id(str(session_id))
        
        if not session:
            raise SessionError(f"Session not found: {session_id}")
            
        # Ensure session is not completed or canceled
        if session["status"] in ["completed", "canceled"]:
            raise SessionError(f"Cannot reschedule {session['status']} session")
            
        # Update session
        update_data = {
            "start_time": start_time,
            "end_time": end_time
        }
        
        updated_session = await update_session(
            session_id=str(session_id),
            update_data=update_data
        )
        
        if not updated_session:
            raise SessionError(f"Failed to reschedule session: {session_id}")
            
        # Update Zoom meeting if available
        if session.get("zoom_link"):
            try:
                # Extract meeting ID from zoom link
                zoom_link = session["zoom_link"]
                meeting_id = zoom_link.split("/j/")[1].split("?")[0]
                
                # Update Zoom meeting
                await update_meeting(
                    meeting_id=meeting_id,
                    start_time=start_time,
                    duration_minutes=int((end_time - start_time).total_seconds() / 60)
                )
                
            except Exception as e:
                logger.error(f"Error updating Zoom meeting: {str(e)}")
                # Continue even if Zoom meeting update fails
                
        # Send update notifications
        asyncio.create_task(send_session_notifications(updated_session, is_reschedule=True))
            
        return updated_session
        
    except SessionError as e:
        # Re-raise session-specific errors
        raise
    except Exception as e:
        logger.error(f"Error rescheduling session: {str(e)}")
        raise SessionError(f"Error rescheduling session: {str(e)}")


async def send_session_notifications(
    session: Dict[str, Any],
    is_reschedule: bool = False
) -> None:
    """
    Send email notifications for a session.
    
    Args:
        session: Session data
        is_reschedule: Whether this is for a rescheduled session
        
    Returns:
        None
    """
    try:
        # Get user and researcher
        user_id = session.get("user_id")
        researcher_id = session.get("researcher_id")
        
        if not user_id or not researcher_id:
            logger.error(f"Missing user_id or researcher_id in session: {session.get('id')}")
            return
            
        user = await get_user_by_id(str(user_id))
        researcher = await get_researcher_by_id(str(researcher_id))
        
        if not user or not researcher:
            logger.error(f"User or researcher not found for session: {session.get('id')}")
            return
            
        # Get paper if applicable
        paper_title = None
        if session.get("paper_id"):
            paper = await get_paper_by_id(str(session.get("paper_id")))
            if paper:
                paper_title = paper.get("title")
                
        # Prepare session data for emails
        email_data = {
            "id": session.get("id"),
            "researcher_name": researcher.get("name"),
            "user_name": user.get("name"),
            "paper_title": paper_title,
            "start_time": session.get("start_time"),
            "end_time": session.get("end_time"),
            "zoom_link": session.get("zoom_link")
        }
        
        # Send emails to user and researcher
        user_email = user.get("email")
        researcher_email = researcher.get("email")
        
        if user_email:
            await send_session_confirmation_email(user_email, email_data)
            
        if researcher_email:
            await send_session_confirmation_email(researcher_email, email_data)
            
        # Schedule reminders if not a reschedule
        if not is_reschedule:
            # Schedule 24-hour reminder
            start_time = session.get("start_time")
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                
            reminder_time = start_time - timedelta(hours=24)
            
            # Only schedule if in the future
            if reminder_time > datetime.now():
                # Here we would ideally use a background job scheduler
                # For now, we'll just log a TODO message
                logger.info(f"TODO: Schedule 24-hour reminder for session {session.get('id')}")
                
                # In a production system, we would use Celery, Redis, or another
                # task scheduler to handle the delayed reminder emails
                
    except Exception as e:
        logger.error(f"Error sending session notifications: {str(e)}") 