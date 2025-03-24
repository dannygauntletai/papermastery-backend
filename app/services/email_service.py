import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.logger import get_logger
from app.core.config import get_settings
from datetime import datetime
from typing import Optional, List, Dict, Any
import jwt
import time
from jinja2 import Environment, PackageLoader, select_autoescape

logger = get_logger(__name__)
settings = get_settings()

# Initialize Jinja2 environment for email templates
try:
    env = Environment(
        loader=PackageLoader('app', 'templates/emails'),
        autoescape=select_autoescape(['html', 'xml'])
    )
except Exception as e:
    logger.error(f"Failed to initialize Jinja2 environment: {str(e)}")
    env = None

async def send_email(
    to_email: str, 
    subject: str, 
    content: str, 
    from_email: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None
) -> bool:
    """
    Send an email using SendGrid.
    
    Args:
        to_email: The recipient's email address
        subject: Email subject
        content: HTML content of the email
        from_email: Sender email (defaults to settings.sendgrid_from_email)
        cc: List of CC recipients
        bcc: List of BCC recipients
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        message = Mail(
            from_email=from_email or settings.sendgrid_from_email,
            to_emails=to_email,
            subject=subject,
            html_content=content
        )
        
        # Add CC recipients if provided
        if cc:
            for cc_email in cc:
                message.add_cc(cc_email)
                
        # Add BCC recipients if provided
        if bcc:
            for bcc_email in bcc:
                message.add_bcc(bcc_email)
        
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            logger.error(
                f"Failed to send email to {to_email}. Status code: {response.status_code}"
            )
            return False
            
    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {str(e)}")
        return False


async def send_waiting_list_confirmation(email: str) -> bool:
    """
    Send a confirmation email to a user who has joined the waiting list.
    
    Args:
        email: The email address of the user
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        message = Mail(
            from_email=settings.sendgrid_from_email,
            to_emails=email,
            subject='Welcome to the Paper Mastery Waiting List',
            html_content="""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; 
            padding: 20px;">
                <h1 style="color: #4F46E5; text-align: center;">Welcome to Paper Mastery!</h1>
                <p>Thank you for joining our waiting list. We're excited to have you on board!</p>
                <p>Paper Mastery is an AI-powered platform that helps you understand research 
                papers step by step, from fundamentals to mastery.</p>
                <p>We'll notify you as soon as we're ready to welcome new users to our 
                platform.</p>
                <p>In the meantime, if you have any questions, feel free to reply to this 
                email.</p>
                <div style="text-align: center; margin-top: 30px;">
                    <p style="color: #6B7280; font-size: 14px;">© Paper Mastery. All rights 
                    reserved.</p>
                </div>
            </div>
            """
        )
        
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Confirmation email sent successfully to {email}")
            return True
        else:
            logger.error(
                f"Failed to send confirmation email to {email}. Status code: {response.status_code}"
            )
            return False
            
    except Exception as e:
        logger.error(f"Error sending confirmation email to {email}: {str(e)}")
        return False


async def send_researcher_outreach_email(
    to_email: str, 
    token: str,
    paper_title: Optional[str] = None,
    user_name: Optional[str] = None
) -> bool:
    """
    Send an outreach email to a researcher inviting them to join the platform.
    
    Args:
        to_email: Researcher's email address
        token: JWT token for registration link
        paper_title: Title of the paper user is interested in (optional)
        user_name: Name of the user requesting the consultation (optional)
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        if env is None:
            raise Exception("Jinja2 environment not initialized")
            
        template = env.get_template('outreach_request.j2')
        registration_url = f"{settings.frontend_url}/register-researcher?token={token}"
        
        # Render template with context data
        context = {
            "registration_url": registration_url,
            "paper_title": paper_title,
            "user_name": user_name or "A Paper Mastery user",
            "platform_name": "Paper Mastery",
            "platform_description": (
                "an AI-powered platform that helps researchers connect with users "
                "interested in their academic papers"
            ),
            "current_year": datetime.now().year
        }
        
        html_content = template.render(**context)
        
        # Send email
        subject = f"Join Paper Mastery as a Consulting Researcher"
        return await send_email(to_email, subject, html_content)
            
    except Exception as e:
        logger.error(f"Error sending outreach email to {to_email}: {str(e)}")
        return False


async def send_session_confirmation_email(
    to_email: str,
    session_data: Dict[str, Any]
) -> bool:
    """
    Send a session confirmation email to a user or researcher.
    
    Args:
        to_email: Recipient's email address
        session_data: Dictionary containing session details
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        if env is None:
            raise Exception("Jinja2 environment not initialized")
            
        template = env.get_template('session_confirmation.j2')
        
        # Format date and time
        start_time = session_data.get("start_time")
        end_time = session_data.get("end_time")
        
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
        # Format date as "Monday, January 1, 2023"
        date_str = start_time.strftime("%A, %B %d, %Y")
        
        # Format time as "10:00 AM - 11:00 AM UTC"
        time_str = (
            f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} "
            f"{start_time.strftime('%Z')}"
        )
        
        # Render template with context data
        context = {
            "session_id": session_data.get("id"),
            "researcher_name": session_data.get("researcher_name"),
            "user_name": session_data.get("user_name"),
            "paper_title": session_data.get("paper_title"),
            "date": date_str,
            "time": time_str,
            "zoom_link": session_data.get("zoom_link"),
            "platform_name": "Paper Mastery",
            "support_email": settings.support_email or settings.sendgrid_from_email,
            "current_year": datetime.now().year
        }
        
        html_content = template.render(**context)
        
        # Send email
        subject = f"Your Paper Mastery Consultation Session Confirmation"
        return await send_email(to_email, subject, html_content)
            
    except Exception as e:
        logger.error(f"Error sending session confirmation email to {to_email}: {str(e)}")
        return False


async def send_session_reminder_email(
    to_email: str,
    session_data: Dict[str, Any],
    hours_before: int = 24
) -> bool:
    """
    Send a session reminder email to a user or researcher.
    
    Args:
        to_email: Recipient's email address
        session_data: Dictionary containing session details
        hours_before: Hours before the session (for message customization)
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        if env is None:
            raise Exception("Jinja2 environment not initialized")
            
        template = env.get_template('session_reminder.j2')
        
        # Format date and time
        start_time = session_data.get("start_time")
        end_time = session_data.get("end_time")
        
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
        # Format date as "Monday, January 1, 2023"
        date_str = start_time.strftime("%A, %B %d, %Y")
        
        # Format time as "10:00 AM - 11:00 AM UTC"
        time_str = (
            f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} "
            f"{start_time.strftime('%Z')}"
        )
        
        # Render template with context data
        context = {
            "session_id": session_data.get("id"),
            "researcher_name": session_data.get("researcher_name"),
            "user_name": session_data.get("user_name"),
            "paper_title": session_data.get("paper_title"),
            "date": date_str,
            "time": time_str,
            "zoom_link": session_data.get("zoom_link"),
            "hours_before": hours_before,
            "platform_name": "Paper Mastery",
            "support_email": settings.support_email or settings.sendgrid_from_email,
            "current_year": datetime.now().year
        }
        
        html_content = template.render(**context)
        
        # Send email
        time_label = "hour" if hours_before == 1 else "hours"
        subject = f"Reminder: Your Paper Mastery Session in {hours_before} {time_label}"
        return await send_email(to_email, subject, html_content)
            
    except Exception as e:
        logger.error(f"Error sending session reminder email to {to_email}: {str(e)}")
        return False


def generate_registration_token(researcher_email: str, outreach_id: str) -> str:
    """
    Generate a JWT token for researcher registration.
    
    Args:
        researcher_email: Email of the researcher
        outreach_id: ID of the outreach request
        
    Returns:
        JWT token as string
    """
    try:
        # Token expiration time (14 days)
        expiration = int(time.time()) + (60 * 60 * 24 * 14)
        
        # Create JWT payload
        payload = {
            "email": researcher_email,
            "outreach_id": outreach_id,
            "exp": expiration
        }
        
        # Generate token using the app's secret key
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
        
        # If token is bytes, convert to string
        if isinstance(token, bytes):
            token = token.decode("utf-8")
            
        return token
        
    except Exception as e:
        logger.error(f"Error generating registration token: {str(e)}")
        raise


def verify_registration_token(token: str) -> Dict[str, Any]:
    """
    Verify a JWT token for researcher registration.
    
    Args:
        token: JWT token
        
    Returns:
        Dictionary with token payload if valid
        
    Raises:
        Exception: If token is invalid or expired
    """
    try:
        # Decode and verify token
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.error("Registration token has expired")
        raise Exception("Registration link has expired. Please request a new one.")
        
    except jwt.InvalidTokenError:
        logger.error("Invalid registration token")
        raise Exception("Invalid registration link. Please request a new one.")
        
    except Exception as e:
        logger.error(f"Error verifying registration token: {str(e)}")
        raise 