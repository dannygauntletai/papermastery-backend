"""Stripe Service for handling payments and subscriptions."""
import stripe
from typing import Dict, Any, Optional
import os
from app.core.config import get_settings
from app.core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Check if we're in a development environment
is_development = settings.APP_ENV == "development"

class StripeService:
    """Service for handling Stripe payments and subscriptions."""
    
    def __init__(self):
        """Initialize the Stripe service with API key."""
        # Check if we have valid Stripe configuration
        missing_config = []
        
        if not settings.STRIPE_SECRET_KEY:
            missing_config.append("STRIPE_SECRET_KEY")
        
        if settings.STRIPE_SUBSCRIPTION_PRICE_ID == "price_test_placeholder":
            missing_config.append("STRIPE_SUBSCRIPTION_PRICE_ID")
        
        # Throw error if any required configuration is missing
        if missing_config:
            error_msg = f"Missing required Stripe configuration: {', '.join(missing_config)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Set the API key
        stripe.api_key = settings.STRIPE_SECRET_KEY
        logger.info("Using Stripe service with provided API keys.")
    
    def create_checkout_session(self, product_type: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """
        Create a Stripe checkout session for subscription or one-time payment.
        
        Args:
            product_type: Type of product ('premium_subscription')
            user_id: The ID of the user making the purchase
            success_url: URL to redirect to after successful payment
            cancel_url: URL to redirect to after canceled payment
            
        Returns:
            Dict containing the checkout session information including URL
        """
        if product_type == 'premium_subscription':
            # Use the price ID from settings - we've already verified it exists in __init__
            price_id = settings.STRIPE_SUBSCRIPTION_PRICE_ID
            logger.info(f"Creating checkout session with price ID: {price_id}")
            
            # Create the checkout session for subscription
            checkout_session = stripe.checkout.Session.create(
                success_url=success_url,
                cancel_url=cancel_url,
                payment_method_types=['card'],
                mode='subscription',
                client_reference_id=user_id,
                line_items=[
                    {
                        'price': price_id,
                        'quantity': 1,
                    }
                ],
                metadata={
                    'user_id': user_id,
                    'product_type': product_type
                }
            )
            
            return {
                'id': checkout_session.id,
                'url': checkout_session.url
            }
        else:
            raise ValueError(f"Unsupported product type: {product_type}")
    
    def check_subscription_status(self, user_id: str) -> bool:
        """
        Check if a user has an active subscription.
        
        Args:
            user_id: The ID of the user to check
            
        Returns:
            Boolean indicating if user has active subscription
        """
        # Use Supabase to query for active subscription
        from app.database.supabase_client import supabase

        logger.info(f"Checking subscription status for user {user_id}")
        
        try:
            # Skip direct auth.users check as it might not be accessible via supabase-py client
            # Just log the user ID we're checking
            logger.info(f"Checking subscription status in Supabase for user ID: {user_id}")
            
            # Query for active subscriptions for this user
            response = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
            
            # If we have any results, the user has an active subscription
            subscriptions = response.data
            has_subscription = len(subscriptions) > 0
            
            if has_subscription:
                logger.info(f"User {user_id} has active subscription: {subscriptions[0]}")
            else:
                # Log all subscriptions regardless of status
                all_subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
                if all_subs.data:
                    logger.info(f"User {user_id} has {len(all_subs.data)} non-active subscriptions: {all_subs.data}")
                else:
                    logger.info(f"User {user_id} has no subscriptions in database")
            
            return has_subscription
        except Exception as e:
            logger.error(f"Error checking subscription status for user {user_id}: {str(e)}")
            # In case of an error, return False to be safe
            return False
    
    def handle_webhook_event(self, event: Dict[str, Any]) -> None:
        """
        Handle Stripe webhook events.
        
        Args:
            event: The Stripe webhook event object
        """
        event_type = event['type']
        
        if event_type == 'checkout.session.completed':
            self._handle_checkout_completed(event['data']['object'])
        elif event_type == 'customer.subscription.created':
            self._handle_subscription_created(event['data']['object'])
        elif event_type == 'customer.subscription.updated':
            self._handle_subscription_updated(event['data']['object'])
        elif event_type == 'customer.subscription.deleted':
            self._handle_subscription_deleted(event['data']['object'])
        elif event_type == 'invoice.payment_succeeded':
            self._handle_payment_succeeded(event['data']['object'])
        elif event_type == 'invoice.payment_failed':
            self._handle_payment_failed(event['data']['object'])
    
    def _handle_checkout_completed(self, session: Dict[str, Any]) -> None:
        """Handle checkout.session.completed event."""
        # Log full session for debugging
        logger.info(f"Processing checkout.session.completed event: {session.get('id')}")
        logger.debug(f"Full session data: {session}")
        
        # Try to get user_id from multiple sources
        # Method 1: From metadata
        user_id = session.get('metadata', {}).get('user_id')
        logger.info(f"User ID from metadata: {user_id}")
        
        # Method 2: From client_reference_id
        if not user_id:
            user_id = session.get('client_reference_id')
            logger.info(f"User ID from client_reference_id: {user_id}")
        
        # Method 3: Try to extract from customer if available
        if not user_id and session.get('customer'):
            try:
                customer = stripe.Customer.retrieve(session.get('customer'))
                user_id = customer.get('metadata', {}).get('user_id')
                logger.info(f"User ID from customer metadata: {user_id}")
            except Exception as e:
                logger.error(f"Error retrieving customer: {str(e)}")
        
        if not user_id:
            logger.warning("Unable to determine user_id for checkout session")
            logger.warning(f"Session details: ID={session.get('id')}, mode={session.get('mode')}")
            # We'll continue anyway to create at least some record
            # Let's use a placeholder ID that will be associated with the customer
            user_id = f"customer_{session.get('customer')}" if session.get('customer') else "unknown"
        
        try:
            # For subscriptions, we need to create both a subscription record and a payment record
            from app.database.supabase_client import supabase
            from datetime import datetime, timedelta
            
            # Save payment record to database
            amount = session.get('amount_total', 0) / 100  # Convert from cents to dollars
            if amount <= 0 and session.get('display_items'):
                # Try to get amount from display items
                for item in session.get('display_items', []):
                    if item.get('amount'):
                        amount = item.get('amount') / 100
                        break
            
            payment_data = {
                "user_id": user_id,
                "amount": amount,
                "status": "completed",
                "transaction_id": session.get('id'),
                "created_at": datetime.now().isoformat(),
            }
            
            # Add subscription_id if available
            if session.get('subscription'):
                payment_data["subscription_id"] = session.get('subscription')
                logger.info(f"Associated with subscription: {session.get('subscription')}")
            
            logger.info(f"Creating payment record: {payment_data}")
            
            # Insert payment record
            payment_result = supabase.table("payments").insert(payment_data).execute()
            logger.info(f"Payment record created: {payment_result.data}")
            
            # For subscription mode, also create a subscription record if it doesn't exist already
            # This is a backup in case the subscription.created webhook fails
            if session.get('mode') == 'subscription' and session.get('subscription'):
                subscription_id = session.get('subscription')
                
                # Check if subscription already exists
                sub_check = supabase.table("subscriptions").select("id").eq("id", subscription_id).execute()
                
                if not sub_check.data:
                    logger.info(f"Creating backup subscription record for {subscription_id}, user_id={user_id}")
                    
                    # Create a subscription that lasts for 30 days from now
                    start_date = datetime.now()
                    end_date = start_date + timedelta(days=30)
                    
                    subscription_data = {
                        "id": subscription_id,
                        "user_id": user_id,
                        "status": "active",
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "created_at": start_date.isoformat()
                    }
                    
                    logger.info(f"Preparing to insert backup subscription data: {subscription_data}")
                    
                    try:
                        # Insert subscription record
                        sub_result = supabase.table("subscriptions").insert(subscription_data).execute()
                        logger.info(f"Backup subscription record created: {sub_result.data}")
                    except Exception as sub_error:
                        logger.error(f"Error creating backup subscription record: {str(sub_error)}")
                        
                        # Try with a generated UUID if Stripe's ID doesn't work with Supabase
                        try:
                            import uuid
                            subscription_data["id"] = str(uuid.uuid4())
                            logger.info(f"Retrying with generated UUID: {subscription_data['id']}")
                            sub_result = supabase.table("subscriptions").insert(subscription_data).execute()
                            logger.info(f"Backup subscription record created with generated UUID: {sub_result.data}")
                        except Exception as uuid_error:
                            logger.error(f"Error creating backup subscription with generated UUID: {str(uuid_error)}")
            
        except Exception as e:
            logger.error(f"Error creating payment/subscription records: {str(e)}")
    
    def _handle_subscription_created(self, subscription: Dict[str, Any]) -> None:
        """Handle customer.subscription.created event."""
        try:
            # Extract subscription info
            subscription_id = subscription.get('id')
            customer_id = subscription.get('customer')
            
            # Log the full subscription object for debugging
            logger.info(f"Processing subscription created event: {subscription_id}")
            logger.debug(f"Full subscription data: {subscription}")
            
            # Try multiple methods to get the user ID
            
            # Method 1: Try to get user_id directly from subscription metadata
            user_id = subscription.get('metadata', {}).get('user_id')
            logger.info(f"User ID from metadata: {user_id}")
            
            # Method 2: Try to get from customer metadata
            if not user_id:
                try:
                    customer = stripe.Customer.retrieve(customer_id)
                    user_id = customer.get('metadata', {}).get('user_id')
                    logger.info(f"User ID from customer metadata: {user_id}")
                except Exception as e:
                    logger.error(f"Error retrieving customer: {str(e)}")
            
            # Method 3: Look for customer mapping in our database
            if not user_id:
                try:
                    from app.database.supabase_client import supabase
                    customer_response = supabase.table("stripe_customers").select("user_id").eq("customer_id", customer_id).execute()
                    if customer_response.data and len(customer_response.data) > 0:
                        user_id = customer_response.data[0].get('user_id')
                        logger.info(f"User ID from database: {user_id}")
                except Exception as e:
                    logger.error(f"Error looking up customer in database: {str(e)}")
            
            # Method 4: Get from checkout session if available
            if not user_id and subscription.get('latest_invoice'):
                try:
                    invoice = stripe.Invoice.retrieve(subscription.get('latest_invoice'))
                    if invoice.get('checkout_session'):
                        session = stripe.checkout.Session.retrieve(invoice.get('checkout_session'))
                        user_id = session.get('client_reference_id')
                        logger.info(f"User ID from checkout session: {user_id}")
                except Exception as e:
                    logger.error(f"Error retrieving invoice/session: {str(e)}")
            
            # If we still don't have a user_id, we can't create the subscription record
            if not user_id:
                logger.warning(f"Unable to determine user_id for subscription {subscription_id}")
                return
                
            # Create the subscription record
            from app.database.supabase_client import supabase
            from datetime import datetime
            
            # Get subscription period info
            start_date = subscription.get('start_date') or subscription.get('created')
            current_period_end = subscription.get('current_period_end')
            
            # Convert timestamps to ISO format if they're Unix timestamps
            from datetime import datetime, timedelta
            start_date_iso = datetime.fromtimestamp(start_date).isoformat() if isinstance(start_date, int) else datetime.now().isoformat()
            end_date_iso = datetime.fromtimestamp(current_period_end).isoformat() if isinstance(current_period_end, int) else (datetime.now() + timedelta(days=30)).isoformat()
            
            subscription_data = {
                "id": subscription_id,
                "user_id": user_id,
                "status": "active",
                "start_date": start_date_iso,
                "end_date": end_date_iso,
                "created_at": datetime.now().isoformat()
            }
            
            logger.info(f"Creating subscription record: {subscription_data}")
            
            # Insert subscription record
            logger.info(f"Creating subscription record in Supabase for user {user_id} with data: {subscription_data}")
            result = supabase.table("subscriptions").insert(subscription_data).execute()
            logger.info(f"Subscription record created for user {user_id}: {result.data}")
            
        except Exception as e:
            logger.error(f"Error creating subscription record: {str(e)}")
    
    def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> None:
        """Handle customer.subscription.updated event."""
        # Update subscription status in database
        # ... database code here ...
        pass
    
    def _handle_subscription_deleted(self, subscription: Dict[str, Any]) -> None:
        """Handle customer.subscription.deleted event."""
        # Mark subscription as canceled in database
        # ... database code here ...
        pass
    
    def _handle_payment_succeeded(self, invoice: Dict[str, Any]) -> None:
        """Handle invoice.payment_succeeded event."""
        # Record successful payment
        # ... database code here ...
        pass
    
    def _handle_payment_failed(self, invoice: Dict[str, Any]) -> None:
        """Handle invoice.payment_failed event."""
        # Record failed payment and update subscription status
        # ... database code here ...
        pass


# Singleton instance
stripe_service = StripeService()