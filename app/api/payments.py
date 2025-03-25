"""API endpoints for payment processing and subscription management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.api.dependencies import get_current_user
from app.core.logger import get_logger
from app.core.config import get_settings

# Set up logger first
logger = get_logger(__name__)

# Get settings
settings = get_settings()

# Set up router
router = APIRouter(prefix="/payments", tags=["payments"])

# Try to import stripe_service, but handle import errors gracefully
stripe_service: Optional[object] = None
try:
    from app.services.stripe_service import stripe_service
except ValueError as e:
    # Missing Stripe configuration
    logger.error(f"Stripe service initialization failed: {str(e)}")
    # stripe_service will remain None


class CheckoutRequest(BaseModel):
    """Request model for creating a Stripe checkout session."""
    productType: str
    returnUrl: Optional[str] = None


class SubscriptionStatusResponse(BaseModel):
    """Response model for subscription status check."""
    hasActiveSubscription: bool


@router.post("/checkout")
async def create_checkout_session(request: CheckoutRequest, current_user: str = Depends(get_current_user)) -> Dict[str, str]:
    """
    Create a Stripe checkout session for subscription payment.
    
    Args:
        request: The checkout request with product type and optional returnUrl
        current_user: The authenticated user ID
        
    Returns:
        Dict containing the checkout session URL
    """
    # Check if stripe_service is available
    if stripe_service is None:
        error_message = "Stripe service is not available - missing required configuration"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)
        
    try:
        # Base URL for redirects
        base_url = "http://localhost:8080"  # Match the frontend port
        
        # Use custom returnUrl if provided, otherwise use default success URL
        success_url = request.returnUrl if request.returnUrl else f"{base_url}/subscription/success"
        cancel_url = f"{base_url}/subscription/cancel"
        
        logger.info(f"Creating checkout session with success_url: {success_url}")
        
        # Create checkout session
        checkout = stripe_service.create_checkout_session(
            product_type=request.productType,
            user_id=current_user,  # current_user is already the user ID string
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        # Make sure the response matches what the frontend expects
        if "url" in checkout:
            return {"url": checkout["url"]}
        else:
            logger.error(f"Missing URL in checkout response: {checkout}")
            raise HTTPException(status_code=500, detail="Invalid checkout session response")
    except ValueError as e:
        # Specific error for missing configuration or validation issues
        error_message = f"Stripe configuration error: {str(e)}"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")


@router.get("/subscription-status")
async def check_subscription_status(current_user: str = Depends(get_current_user)) -> SubscriptionStatusResponse:
    """
    Check if the current user has an active subscription.
    
    Args:
        current_user: The authenticated user ID
        
    Returns:
        SubscriptionStatusResponse indicating if user has an active subscription
    """
    # Check if stripe_service is available
    if stripe_service is None:
        error_message = "Stripe service is not available - missing required configuration"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)
        
    try:
        is_subscribed = stripe_service.check_subscription_status(current_user)
        return SubscriptionStatusResponse(hasActiveSubscription=is_subscribed)
    except ValueError as e:
        # Specific error for missing configuration or validation issues
        error_message = f"Stripe configuration error: {str(e)}"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Error checking subscription status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check subscription status: {str(e)}")


class CancelSubscriptionResponse(BaseModel):
    """Response model for subscription cancellation."""
    success: bool
    message: str
    end_date: Optional[str] = None


@router.post("/cancel-subscription")
async def cancel_subscription(current_user: str = Depends(get_current_user)) -> CancelSubscriptionResponse:
    """
    Cancel the current user's active subscription.
    
    Args:
        current_user: The authenticated user ID
        
    Returns:
        CancelSubscriptionResponse with cancellation status
    """
    # Check if stripe_service is available
    if stripe_service is None:
        error_message = "Stripe service is not available - missing required configuration"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)
        
    try:
        result = stripe_service.cancel_subscription(current_user)
        return CancelSubscriptionResponse(
            success=result.get("success", False),
            message=result.get("message", "Error processing cancellation"),
            end_date=result.get("end_date")
        )
    except ValueError as e:
        # Specific error for missing configuration or validation issues
        error_message = f"Stripe configuration error: {str(e)}"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")


@router.post("/webhook")
async def handle_webhook(request: Request) -> Dict[str, str]:
    """
    Handle Stripe webhook events.
    
    Args:
        request: The HTTP request containing the webhook payload
        
    Returns:
        Dict with success message
    """
    try:
        # Get the webhook payload
        payload_bytes = await request.body()
        payload = await request.json()
        
        # Get Stripe signature from headers
        sig_header = request.headers.get("stripe-signature", "")
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        
        logger.info(f"Received webhook event: {payload.get('type', 'unknown')}")
        
        # If we have a webhook secret, verify the signature
        if webhook_secret and sig_header:
            try:
                import stripe
                event = stripe.Webhook.construct_event(
                    payload_bytes, sig_header, webhook_secret
                )
                logger.info(f"Webhook signature verification passed: {event['id']}")
                payload = event
            except stripe.error.SignatureVerificationError as e:
                logger.error(f"⚠️ Webhook signature verification failed: {str(e)}")
                raise HTTPException(status_code=400, detail="Invalid webhook signature")
            except Exception as e:
                logger.error(f"⚠️ Error verifying webhook signature: {str(e)}")
        else:
            logger.info("No webhook secret configured or no signature header - skipping verification")
            # For a proper webhook, we should always have these, so let's log a warning
            if not webhook_secret:
                logger.warning("STRIPE_WEBHOOK_SECRET is not configured. Set this in your environment variables.")
            if not sig_header:
                logger.warning("No stripe-signature header in request. Check your webhook configuration in Stripe dashboard.")
                
        # Verify stripe_service is initialized
        if not stripe_service:
            error_message = "Stripe service is not available - cannot process webhook"
            logger.error(error_message)
            raise HTTPException(status_code=500, detail=error_message)
                
        # Handle the event
        stripe_service.handle_webhook_event(payload)
        
        return {"status": "success", "event_type": payload.get('type', 'unknown')}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process webhook: {str(e)}")


class TestSubscriptionRequest(BaseModel):
    """Request model for creating a test subscription."""
    sessionId: str


@router.post("/create-test-subscription")
async def create_test_subscription(
    request: TestSubscriptionRequest, 
    current_user: str = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Create a test subscription directly in the database.
    This is only for development/testing purposes.
    
    Args:
        request: The test subscription request
        current_user: The authenticated user ID
        
    Returns:
        Dict with success message
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    try:
        # Use Supabase client to insert a subscription
        from app.database.supabase_client import supabase
        from datetime import datetime, timedelta
        
        # Create a subscription that lasts for 30 days
        start_date = datetime.now()
        end_date = start_date + timedelta(days=30)
        
        # Create subscription data
        subscription_data = {
            "id": f"test_sub_{request.sessionId[-8:]}",  # Generate a pseudo-random ID
            "user_id": current_user,
            "status": "active",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "created_at": start_date.isoformat(),
            "stripe_id": f"sub_test_{request.sessionId[-8:]}"  # Add a fake stripe ID
        }
        
        logger.info(f"Preparing to insert test subscription data: {subscription_data}")
        
        try:
            # Check for existing test subscription for this user
            existing_sub = supabase.table("subscriptions").select("id").eq("user_id", current_user).eq("status", "active").execute()
            if existing_sub.data and len(existing_sub.data) > 0:
                logger.info(f"User {current_user} already has an active subscription, id={existing_sub.data[0].get('id')}")
                return {
                    "status": "success", 
                    "message": "User already has an active subscription",
                    "existing_subscription": existing_sub.data[0]
                }
            
            # Insert subscription record
            result = supabase.table("subscriptions").insert(subscription_data).execute()
            
            # Check if we already have a test payment with this transaction ID
            test_tx_id = f"test_tx_{request.sessionId[-8:]}"
            existing_payment = supabase.table("payments").select("id").eq("transaction_id", test_tx_id).execute()
            if existing_payment.data and len(existing_payment.data) > 0:
                logger.info(f"Payment for test transaction {test_tx_id} already exists, skipping duplicate creation")
                return {
                    "status": "success", 
                    "message": "Test subscription created (payment already exists)",
                    "subscription": result.data[0],
                }
            
            # Also create a payment record
            payment_data = {
                "user_id": current_user,
                "amount": 10.00,  # Standard price
                "status": "completed",
                "transaction_id": test_tx_id,
                "subscription_id": subscription_data["id"],  # Link to subscription
                "stripe_subscription_id": f"sub_test_{request.sessionId[-8:]}",  # Add a fake stripe subscription ID
                "created_at": start_date.isoformat()
            }
            
            # Insert payment record
            payment_result = supabase.table("payments").insert(payment_data).execute()
            
            logger.info(f"Created test subscription for user {current_user}")
            logger.info(f"Subscription record: {result.data}")
            logger.info(f"Payment record: {payment_result.data}")
            
            return {
                "status": "success", 
                "message": "Test subscription created",
                "subscription": result.data[0],
                "payment": payment_result.data[0]
            }
        except Exception as e:
            logger.error(f"Error creating test subscription: {str(e)}")
            
            # Try with a UUID
            try:
                import uuid
                subscription_data["id"] = str(uuid.uuid4())
                logger.info(f"Retrying with UUID: {subscription_data['id']}")
                result = supabase.table("subscriptions").insert(subscription_data).execute()
                
                payment_data = {
                    "user_id": current_user,
                    "amount": 10.00,
                    "status": "completed",
                    "transaction_id": f"test_tx_{request.sessionId[-8:]}",
                    "subscription_id": subscription_data["id"],
                    "stripe_subscription_id": f"sub_test_{request.sessionId[-8:]}",  # Add a fake stripe subscription ID
                    "created_at": start_date.isoformat()
                }
                
                payment_result = supabase.table("payments").insert(payment_data).execute()
                
                logger.info(f"Created test subscription with UUID for user {current_user}")
                return {
                    "status": "success", 
                    "message": "Test subscription created with UUID",
                    "subscription": result.data[0],
                    "payment": payment_result.data[0]
                }
            except Exception as inner_e:
                logger.error(f"Error creating test subscription with UUID: {str(inner_e)}")
                raise HTTPException(status_code=500, detail=f"Failed to create test subscription: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Error creating test subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create test subscription: {str(e)}")