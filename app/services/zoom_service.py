from typing import Dict, Any, Optional
import httpx
import jwt
import time
from datetime import datetime, timedelta

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.exceptions import ServiceError

logger = get_logger(__name__)
settings = get_settings()

class ZoomServiceError(ServiceError):
    """Exception raised for errors in the Zoom service."""
    pass

async def create_zoom_meeting(
    topic: str,
    start_time: datetime,
    duration_minutes: int = 60,
    timezone: str = "UTC",
    agenda: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a Zoom meeting using the Zoom API.
    
    Args:
        topic: Meeting topic/title
        start_time: Meeting start time as datetime
        duration_minutes: Meeting duration in minutes (default: 60)
        timezone: Timezone for meeting (default: UTC)
        agenda: Meeting agenda/description
        
    Returns:
        Dictionary with meeting details including join_url
        
    Raises:
        Exception: If there's an error creating the meeting
    """
    try:
        # Generate JWT token for Zoom API authentication
        token = generate_jwt_token()
        
        # Format start time for Zoom API
        formatted_start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Prepare meeting data
        meeting_data = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "start_time": formatted_start_time,
            "duration": duration_minutes,
            "timezone": timezone,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": True,
                "mute_upon_entry": False,
                "waiting_room": False,
                "auto_recording": "none",
            }
        }
        
        # Add agenda if provided
        if agenda:
            meeting_data["agenda"] = agenda
            
        # Call Zoom API to create meeting
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = await client.post(
                "https://api.zoom.us/v2/users/me/meetings",
                json=meeting_data,
                headers=headers
            )
            
            if response.status_code == 201:
                meeting = response.json()
                logger.info(f"Created Zoom meeting: {meeting.get('id')}")
                return meeting
            else:
                logger.error(f"Failed to create Zoom meeting: {response.text}")
                raise Exception(f"Failed to create Zoom meeting: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error creating Zoom meeting: {str(e)}")
        raise

def generate_jwt_token() -> str:
    """
    Generate a JWT token for Zoom API authentication.
    
    Returns:
        JWT token as string
    """
    try:
        # Get API key and secret from settings
        api_key = settings.zoom_api_key
        api_secret = settings.zoom_api_secret
        
        # Token expiration time (1 minute)
        expiration = int(time.time()) + 60
        
        # Create JWT payload
        payload = {
            "iss": api_key,
            "exp": expiration
        }
        
        # Generate token
        token = jwt.encode(payload, api_secret, algorithm="HS256")
        
        # If token is bytes, convert to string
        if isinstance(token, bytes):
            token = token.decode("utf-8")
            
        return token
        
    except Exception as e:
        logger.error(f"Error generating Zoom JWT token: {str(e)}")
        raise

async def get_meeting(meeting_id: str) -> Dict[str, Any]:
    """
    Get Zoom meeting details.
    
    Args:
        meeting_id: Zoom meeting ID
        
    Returns:
        Dictionary with meeting details
        
    Raises:
        Exception: If there's an error retrieving the meeting
    """
    try:
        # Generate JWT token for Zoom API authentication
        token = generate_jwt_token()
        
        # Call Zoom API to get meeting
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = await client.get(
                f"https://api.zoom.us/v2/meetings/{meeting_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                meeting = response.json()
                return meeting
            else:
                logger.error(f"Failed to get Zoom meeting: {response.text}")
                raise Exception(f"Failed to get Zoom meeting: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error getting Zoom meeting: {str(e)}")
        raise

async def delete_meeting(meeting_id: str) -> bool:
    """
    Delete a Zoom meeting.
    
    Args:
        meeting_id: Zoom meeting ID
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        Exception: If there's an error deleting the meeting
    """
    try:
        # Generate JWT token for Zoom API authentication
        token = generate_jwt_token()
        
        # Call Zoom API to delete meeting
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = await client.delete(
                f"https://api.zoom.us/v2/meetings/{meeting_id}",
                headers=headers
            )
            
            if response.status_code == 204:
                logger.info(f"Deleted Zoom meeting: {meeting_id}")
                return True
            else:
                logger.error(f"Failed to delete Zoom meeting: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error deleting Zoom meeting: {str(e)}")
        raise

async def update_meeting(
    meeting_id: str,
    topic: Optional[str] = None,
    start_time: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
    timezone: Optional[str] = None,
    agenda: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update a Zoom meeting.
    
    Args:
        meeting_id: Zoom meeting ID
        topic: New meeting topic/title
        start_time: New meeting start time
        duration_minutes: New meeting duration in minutes
        timezone: New timezone for meeting
        agenda: New meeting agenda/description
        
    Returns:
        Dictionary with updated meeting details
        
    Raises:
        Exception: If there's an error updating the meeting
    """
    try:
        # Generate JWT token for Zoom API authentication
        token = generate_jwt_token()
        
        # Prepare meeting data with only provided fields
        meeting_data = {}
        
        if topic:
            meeting_data["topic"] = topic
            
        if start_time:
            meeting_data["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%S")
            
        if duration_minutes:
            meeting_data["duration"] = duration_minutes
            
        if timezone:
            meeting_data["timezone"] = timezone
            
        if agenda:
            meeting_data["agenda"] = agenda
            
        # Call Zoom API to update meeting
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = await client.patch(
                f"https://api.zoom.us/v2/meetings/{meeting_id}",
                json=meeting_data,
                headers=headers
            )
            
            if response.status_code == 204:
                # Get updated meeting details
                updated_meeting = await get_meeting(meeting_id)
                logger.info(f"Updated Zoom meeting: {meeting_id}")
                return updated_meeting
            else:
                logger.error(f"Failed to update Zoom meeting: {response.text}")
                raise Exception(f"Failed to update Zoom meeting: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error updating Zoom meeting: {str(e)}")
        raise 