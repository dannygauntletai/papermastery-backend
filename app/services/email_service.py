import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.logger import get_logger
from app.core.config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
from typing import Optional, List

logger = get_logger(__name__)

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
        from_email: Sender email (defaults to SENDGRID_FROM_EMAIL)
        cc: List of CC recipients
        bcc: List of BCC recipients
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        message = Mail(
            from_email=from_email or SENDGRID_FROM_EMAIL,
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
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            logger.error(f"Failed to send email to {to_email}. Status code: {response.status_code}")
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
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=email,
            subject='Welcome to the Paper Mastery Waiting List',
            html_content="""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #4F46E5; text-align: center;">Welcome to Paper Mastery!</h1>
                <p>Thank you for joining our waiting list. We're excited to have you on board!</p>
                <p>Paper Mastery is an AI-powered platform that helps you understand research papers step by step, from fundamentals to mastery.</p>
                <p>We'll notify you as soon as we're ready to welcome new users to our platform.</p>
                <p>In the meantime, if you have any questions, feel free to reply to this email.</p>
                <div style="text-align: center; margin-top: 30px;">
                    <p style="color: #6B7280; font-size: 14px;">© Paper Mastery. All rights reserved.</p>
                </div>
            </div>
            """
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Confirmation email sent successfully to {email}")
            return True
        else:
            logger.error(f"Failed to send confirmation email to {email}. Status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending confirmation email to {email}: {str(e)}")
        return False 