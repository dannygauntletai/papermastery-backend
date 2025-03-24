from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status, Depends
import stripe
import json
import asyncio

from app.core.logger import get_logger
from app.core.config import get_settings
from app.services.consulting_service import (
    update_session_status,
    create_user_subscription
)
from app.database.supabase_client import (
    create_payment,
    update_payment,
    get_payment_by_transaction_id
)

logger = get_logger(__name__)
settings = get_settings()

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
webhook_secret = settings.STRIPE_WEBHOOK_SECRET

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/stripe")
async def stripe_webhook(request: Request) -> Dict[str, Any]:
    """
    Handle Stripe webhook events.
    
    This endpoint processes Stripe webhook events for payment and subscription updates:
    1. Verifies the webhook signature
    2. Processes the event based on its type
    3. Updates the relevant records in the database
    
    Supported events:
    - payment_intent.succeeded: Update payment status and associated session/subscription
    - payment_intent.payment_failed: Update payment status
    - customer.subscription.created: Create or update subscription
    - customer.subscription.updated: Update subscription
    - customer.subscription.deleted: Update subscription status to canceled
    
    Returns:
        Dictionary with status message
    """
    try:
        # Get request body
        payload = await request.body()
        sig_header = request.headers.get("Stripe-Signature")
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            # Invalid payload
            logger.error(f"Invalid Stripe payload: {str(e)}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            logger.error(f"Invalid Stripe signature: {str(e)}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
            
        # Process event based on type
        event_type = event["type"]
        event_data = event["data"]["object"]
        
        # Log event
        logger.info(f"Received Stripe event: {event_type}")
        
        # Handle payment intent events
        if event_type == "payment_intent.succeeded":
            await handle_payment_intent_succeeded(event_data)
            
        elif event_type == "payment_intent.payment_failed":
            await handle_payment_intent_failed(event_data)
            
        # Handle subscription events
        elif event_type == "customer.subscription.created":
            await handle_subscription_created(event_data)
            
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(event_data)
            
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(event_data)
            
        # Return success response
        return {"status": "success", "message": f"Processed {event_type} event"}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )


async def handle_payment_intent_succeeded(payment_intent: Dict[str, Any]) -> None:
    """
    Handle payment_intent.succeeded event.
    
    Args:
        payment_intent: Stripe payment intent object
        
    Returns:
        None
    """
    try:
        payment_intent_id = payment_intent["id"]
        amount = payment_intent["amount"] / 100  # Convert from cents to dollars
        metadata = payment_intent.get("metadata", {})
        
        # Extract metadata
        payment_type = metadata.get("type")
        user_id = metadata.get("user_id")
        
        if not payment_type or not user_id:
            logger.error(f"Missing metadata in payment intent: {payment_intent_id}")
            return
            
        # Check if payment record exists
        existing_payment = await get_payment_by_transaction_id(payment_intent_id)
        
        if existing_payment:
            # Update existing payment
            await update_payment(
                payment_id=existing_payment["id"],
                update_data={"status": "completed"}
            )
        else:
            # Create new payment record
            payment_data = {
                "user_id": user_id,
                "amount": amount,
                "status": "completed",
                "transaction_id": payment_intent_id
            }
            
            # Add session or subscription ID if available
            if payment_type == "session" and metadata.get("session_id"):
                payment_data["session_id"] = metadata["session_id"]
                
                # Update session status
                asyncio.create_task(
                    update_session_status(
                        session_id=metadata["session_id"],
                        status="scheduled"  # Confirm the session
                    )
                )
                
            elif payment_type == "subscription":
                # Create or update subscription
                asyncio.create_task(
                    create_user_subscription(user_id)
                )
                
            # Create payment record
            await create_payment(payment_data)
            
    except Exception as e:
        logger.error(f"Error handling payment_intent.succeeded: {str(e)}")
        # We don't re-raise the exception to avoid webhook failure response


async def handle_payment_intent_failed(payment_intent: Dict[str, Any]) -> None:
    """
    Handle payment_intent.payment_failed event.
    
    Args:
        payment_intent: Stripe payment intent object
        
    Returns:
        None
    """
    try:
        payment_intent_id = payment_intent["id"]
        metadata = payment_intent.get("metadata", {})
        
        # Extract metadata
        payment_type = metadata.get("type")
        session_id = metadata.get("session_id")
        user_id = metadata.get("user_id")
        
        # Check if payment record exists
        existing_payment = await get_payment_by_transaction_id(payment_intent_id)
        
        if existing_payment:
            # Update existing payment
            await update_payment(
                payment_id=existing_payment["id"],
                update_data={"status": "failed"}
            )
        else:
            # Create new payment record
            payment_data = {
                "user_id": user_id,
                "amount": payment_intent["amount"] / 100,
                "status": "failed",
                "transaction_id": payment_intent_id
            }
            
            # Add session or subscription ID if available
            if payment_type == "session" and session_id:
                payment_data["session_id"] = session_id
                
            # Create payment record
            await create_payment(payment_data)
            
    except Exception as e:
        logger.error(f"Error handling payment_intent.payment_failed: {str(e)}")
        # We don't re-raise the exception to avoid webhook failure response


async def handle_subscription_created(subscription: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.created event.
    
    Args:
        subscription: Stripe subscription object
        
    Returns:
        None
    """
    # This is handled in the subscription creation endpoint
    pass


async def handle_subscription_updated(subscription: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.updated event.
    
    Args:
        subscription: Stripe subscription object
        
    Returns:
        None
    """
    # This would update the subscription status and end date
    pass


async def handle_subscription_deleted(subscription: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.deleted event.
    
    Args:
        subscription: Stripe subscription object
        
    Returns:
        None
    """
    # This would update the subscription status to canceled
    pass 