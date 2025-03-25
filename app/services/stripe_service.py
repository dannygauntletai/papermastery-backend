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
    
    def cancel_subscription(self, user_id: str) -> Dict[str, Any]:
        """
        Cancel a user's subscription.
        
        Args:
            user_id: The ID of the user whose subscription to cancel
            
        Returns:
            Dict with cancellation status and message
        """
        from app.database.supabase_client import supabase
        
        logger.info(f"Cancelling subscription for user {user_id}")
        
        try:
            # First get the active subscription from our database
            sub_response = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
            
            if not sub_response.data or len(sub_response.data) == 0:
                logger.warning(f"No active subscription found for user {user_id}")
                return {"success": False, "message": "No active subscription found"}
            
            subscription = sub_response.data[0]
            db_subscription_id = subscription.get('id')
            stripe_subscription_id = subscription.get('stripe_id')
            
            if not stripe_subscription_id:
                logger.warning(f"No Stripe subscription ID found for local subscription {db_subscription_id}")
                
                # Just mark it as canceled in our database
                update_response = supabase.table("subscriptions").update({"status": "canceled"}).eq("id", db_subscription_id).execute()
                logger.info(f"Marked subscription {db_subscription_id} as canceled in database only")
                
                return {"success": True, "message": "Subscription canceled in database", "database_only": True}
            
            # Cancel subscription in Stripe
            try:
                # Get the customer ID for this subscription to verify it belongs to this user
                customer_response = supabase.table("stripe_customers").select("customer_id").eq("user_id", user_id).execute()
                if customer_response.data and len(customer_response.data) > 0:
                    customer_id = customer_response.data[0].get('customer_id')
                    
                    # Retrieve the subscription from Stripe to verify the customer
                    stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                    
                    # Verify the subscription belongs to this customer
                    if stripe_sub.customer != customer_id:
                        logger.warning(f"Subscription {stripe_subscription_id} does not belong to customer {customer_id}")
                        return {"success": False, "message": "Subscription verification failed"}
                    
                    # Cancel the subscription at period end to avoid prorated charges
                    stripe.Subscription.modify(
                        stripe_subscription_id,
                        cancel_at_period_end=True
                    )
                    
                    logger.info(f"Canceled Stripe subscription {stripe_subscription_id} at period end")
                    
                    # Update our database to mark subscription as canceled
                    update_response = supabase.table("subscriptions").update({"status": "canceled"}).eq("id", db_subscription_id).execute()
                    logger.info(f"Marked subscription {db_subscription_id} as canceled in database")
                    
                    return {
                        "success": True, 
                        "message": "Subscription canceled successfully. You'll have access until the end of your billing period.",
                        "end_date": subscription.get('end_date')
                    }
            except Exception as stripe_error:
                logger.error(f"Error canceling Stripe subscription: {str(stripe_error)}")
                return {"success": False, "message": f"Error canceling subscription: {str(stripe_error)}"}
            
        except Exception as e:
            logger.error(f"Error canceling subscription for user {user_id}: {str(e)}")
            return {"success": False, "message": f"Error canceling subscription: {str(e)}"}

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
                subscription = subscriptions[0]
                # Log subscription info
                subscription_id = subscription.get('id', 'none')
                logger.info(f"User {user_id} has active subscription: id={subscription_id}")
                return True
            else:
                # Check if the user has any non-active subscriptions
                all_subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
                if all_subs.data:
                    logger.info(f"User {user_id} has {len(all_subs.data)} non-active subscriptions: {all_subs.data}")
                else:
                    logger.info(f"User {user_id} has no subscriptions in database")
                    
                    # Try a direct check with Stripe as a fallback
                    # This is useful when webhooks fail but the user has an active subscription in Stripe
                    try:
                        # Query Stripe for active subscriptions for this customer
                        # First get the customer ID for this user
                        customer_response = supabase.table("stripe_customers").select("customer_id").eq("user_id", user_id).execute()
                        if customer_response.data and len(customer_response.data) > 0:
                            customer_id = customer_response.data[0].get('customer_id')
                            if customer_id:
                                # Query Stripe for active subscriptions
                                active_subscriptions = stripe.Subscription.list(
                                    customer=customer_id,
                                    status='active',
                                    limit=1
                                )
                                
                                # If we find any active subscriptions, create a record in our database
                                if active_subscriptions and active_subscriptions.data:
                                    stripe_sub = active_subscriptions.data[0]
                                    stripe_subscription_id = stripe_sub.id
                                    
                                    # Check if we already have an active subscription for this user
                                    existing_sub = supabase.table("subscriptions").select("id").eq("user_id", user_id).eq("status", "active").execute()
                                    if existing_sub.data:
                                        logger.info(f"User already has an active subscription, id={existing_sub.data[0].get('id')}")
                                        return True
                                    
                                    # Create a UUID for our database
                                    import uuid
                                    db_sub_id = str(uuid.uuid4())
                                    
                                    # Convert timestamps
                                    from datetime import datetime
                                    start_date = datetime.fromtimestamp(stripe_sub.start_date).isoformat() if hasattr(stripe_sub, 'start_date') else datetime.now().isoformat()
                                    end_date = datetime.fromtimestamp(stripe_sub.current_period_end).isoformat() if hasattr(stripe_sub, 'current_period_end') else (datetime.now() + timedelta(days=30)).isoformat()
                                    
                                    # Create subscription record
                                    sub_data = {
                                        "id": db_sub_id,
                                        "stripe_id": stripe_subscription_id,
                                        "user_id": user_id,
                                        "status": "active",
                                        "start_date": start_date,
                                        "end_date": end_date,
                                        "created_at": datetime.now().isoformat()
                                    }
                                    
                                    # Insert it
                                    supabase_result = supabase.table("subscriptions").insert(sub_data).execute()
                                    logger.info(f"Created missing subscription record from Stripe: {sub_data}")
                                    logger.info(f"Supabase result: {supabase_result.data}")
                                    return True
                    except Exception as stripe_error:
                        logger.error(f"Error checking Stripe for active subscriptions: {str(stripe_error)}")
            
            return False
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
            # Use the app-wide supabase client
            from app.database.supabase_client import supabase
            from datetime import datetime, timedelta
            
            # Check if we already processed this checkout session
            session_id = session.get('id')
            existing_payment = supabase.table("payments").select("id").eq("transaction_id", session_id).execute()
            if existing_payment.data and len(existing_payment.data) > 0:
                logger.info(f"Payment for checkout session {session_id} already exists, skipping duplicate creation")
                return
                
            # Check if there's already an invoice payment for this subscription
            # This is a more reliable transaction ID than the checkout session
            subscription_id = session.get('subscription')
            if subscription_id:
                # Check if there's already a payment with this subscription ID that isn't a cs_test_ payment
                existing_sub_payment = supabase.table("payments").select("*").eq("stripe_subscription_id", subscription_id).execute()
                if existing_sub_payment.data:
                    for payment in existing_sub_payment.data:
                        transaction_id = payment.get('transaction_id', '')
                        if transaction_id.startswith('in_'):  # Invoice payment
                            logger.info(f"Found invoice payment for subscription {subscription_id}, skipping checkout session payment")
                            return
                
            # Save payment record to database
            amount = session.get('amount_total', 0) / 100  # Convert from cents to dollars
            if amount <= 0 and session.get('display_items'):
                # Try to get amount from display items
                for item in session.get('display_items', []):
                    if item.get('amount'):
                        amount = item.get('amount') / 100
                        break
            
            import uuid
            
            # Generate UUIDs for payment and subscription
            payment_id = str(uuid.uuid4())
            subscription_id = str(uuid.uuid4()) if session.get('subscription') else None
            
            payment_data = {
                "id": payment_id,  # Use UUID for payment ID
                "user_id": user_id,
                "amount": amount,
                "status": "completed",
                "transaction_id": session.get('id'),
                "created_at": datetime.now().isoformat(),
            }
            
            # Store Stripe subscription ID
            if session.get('subscription'):
                stripe_subscription_id = session.get('subscription')
                payment_data["stripe_subscription_id"] = stripe_subscription_id
                
                # Don't link with subscription initially - we'll update it after the subscription is created
                logger.info(f"Associated payment with stripe subscription: {stripe_subscription_id}, will link to database ID later")
                
                # Store customer info in stripe_customers table
                if session.get('customer'):
                    customer_id = session.get('customer')
                    try:
                        # Check if we already have this customer
                        customer_check = supabase.table("stripe_customers").select("id").eq("customer_id", customer_id).execute()
                        
                        if not customer_check.data:
                            # Create a new customer record
                            customer_data = {
                                "id": str(uuid.uuid4()),
                                "user_id": user_id,
                                "customer_id": customer_id,
                                "created_at": datetime.now().isoformat()
                            }
                            
                            # First check if table exists by trying a select
                            try:
                                supabase.table("stripe_customers").select("id").limit(1).execute()
                                # If it didn't throw an error, insert the data
                                customer_result = supabase.table("stripe_customers").insert(customer_data).execute()
                                logger.info(f"Created customer record: {customer_result.data}")
                            except Exception as e:
                                logger.warning(f"Could not access stripe_customers table (may not exist yet): {str(e)}")
                    except Exception as e:
                        logger.error(f"Error creating customer record: {str(e)}")
            
            logger.info(f"Creating payment record: {payment_data}")
            
            # Insert payment record with all fields
            payment_result = supabase.table("payments").insert(payment_data).execute()
            logger.info(f"Payment record created: {payment_result.data}")
            
            # For subscription mode, also create a subscription record if it doesn't exist already
            # This is a backup in case the subscription.created webhook fails
            if session.get('mode') == 'subscription' and session.get('subscription'):
                stripe_subscription_id = session.get('subscription')
                
                # Check if subscription already exists for this user
                sub_check = supabase.table("subscriptions").select("id").eq("user_id", user_id).eq("status", "active").execute()
                
                if not sub_check.data:
                    logger.info(f"Creating backup subscription record for {stripe_subscription_id}, user_id={user_id}")
                    
                    # Create a subscription that lasts for 30 days from now
                    start_date = datetime.now()
                    end_date = start_date + timedelta(days=30)
                    
                    subscription_data = {
                        "id": subscription_id,  # Use UUID as ID
                        "user_id": user_id,
                        "status": "active",
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "created_at": start_date.isoformat(),
                        "stripe_id": stripe_subscription_id  # Add the Stripe subscription ID
                    }
                    
                    logger.info(f"Preparing to insert backup subscription data: {subscription_data}")
                    
                    try:
                        # Insert subscription record
                        sub_result = supabase.table("subscriptions").insert(subscription_data).execute()
                        logger.info(f"Backup subscription record created: {sub_result.data}")
                        
                        # Now try to update any payment records that reference this subscription
                        if sub_result.data and stripe_subscription_id:
                            try:
                                payment_update = {
                                    "subscription_id": subscription_id
                                }
                                update_result = supabase.table("payments").update(payment_update).eq("stripe_subscription_id", stripe_subscription_id).execute()
                                logger.info(f"Updated payment records for subscription: {update_result.data}")
                            except Exception as payment_update_error:
                                logger.error(f"Error updating payment records: {str(payment_update_error)}")
                    except Exception as sub_error:
                        logger.error(f"Error creating backup subscription record: {str(sub_error)}")
            
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
                    # Use the app-wide supabase client
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
            # Use the app-wide supabase client
            from app.database.supabase_client import supabase
            from datetime import datetime
            
            # Get subscription period info
            start_date = subscription.get('start_date') or subscription.get('created')
            current_period_end = subscription.get('current_period_end')
            
            # Convert timestamps to ISO format if they're Unix timestamps
            from datetime import datetime, timedelta
            start_date_iso = datetime.fromtimestamp(start_date).isoformat() if isinstance(start_date, int) else datetime.now().isoformat()
            end_date_iso = datetime.fromtimestamp(current_period_end).isoformat() if isinstance(current_period_end, int) else (datetime.now() + timedelta(days=30)).isoformat()
            
            # Generate a UUID for the subscription record
            import uuid
            db_subscription_id = str(uuid.uuid4())
            
            subscription_data = {
                "id": db_subscription_id,  # Use UUID for database ID
                "user_id": user_id,
                "status": "active",
                "start_date": start_date_iso,
                "end_date": end_date_iso,
                "created_at": datetime.now().isoformat(),
                "stripe_id": subscription_id  # Add the Stripe subscription ID
            }
            
            logger.info(f"Creating subscription record: {subscription_data}")
            
            # First check if subscription already exists by user ID
            existing_sub = supabase.table("subscriptions").select("id").eq("user_id", user_id).eq("status", "active").execute()
            if existing_sub.data:
                logger.info(f"Active subscription for user {user_id} already exists, skipping creation")
                return
            
            # Insert subscription record
            logger.info(f"Creating subscription record in Supabase for user {user_id} with data: {subscription_data}")
            result = supabase.table("subscriptions").insert(subscription_data).execute()
            logger.info(f"Subscription record created for user {user_id}: {result.data}")
            
        except Exception as e:
            logger.error(f"Error creating subscription record: {str(e)}")
    
    def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> None:
        """Handle customer.subscription.updated event."""
        try:
            # Extract subscription info
            subscription_id = subscription.get('id')
            status = subscription.get('status')
            cancel_at_period_end = subscription.get('cancel_at_period_end', False)
            
            logger.info(f"Processing subscription.updated event: {subscription_id}, status={status}, cancel_at_period_end={cancel_at_period_end}")
            logger.debug(f"Full subscription data: {subscription}")
            
            if not subscription_id:
                logger.error("Subscription ID missing from update event")
                return
                
            # Use the app-wide supabase client
            from app.database.supabase_client import supabase
            
            # Map Stripe status to our status, considering cancel_at_period_end
            status_map = {
                'active': 'active' if not cancel_at_period_end else 'canceled',  # Mark as canceled if cancel_at_period_end is True
                'past_due': 'active',  # Still considered active but needs payment
                'unpaid': 'expired',
                'canceled': 'canceled',
                'incomplete': 'active',  # Still in trial/setup
                'incomplete_expired': 'expired',
                'trialing': 'active'
            }
            
            db_status = status_map.get(status, 'active')
            if cancel_at_period_end and db_status == 'active':
                db_status = 'canceled'
                logger.info(f"Subscription is set to cancel at period end, setting status to {db_status}")
            
            # Get the current period end as the end_date
            current_period_end = subscription.get('current_period_end')
            end_date = None
            
            if current_period_end:
                from datetime import datetime
                end_date = datetime.fromtimestamp(current_period_end).isoformat()
            
            # First try to find and update by stripe_id (most reliable method)
            try:
                # Look up subscription by stripe_id
                sub_check = supabase.table("subscriptions").select("id").eq("stripe_id", subscription_id).execute()
                if sub_check.data and len(sub_check.data) > 0:
                    # We found existing subscription(s), update status
                    update_data = {"status": db_status}
                    if end_date:
                        update_data["end_date"] = end_date
                    
                    # Update all subscriptions with this stripe_id
                    for existing_sub in sub_check.data:
                        sub_id = existing_sub.get('id')
                        logger.info(f"Updating existing subscription {sub_id} with stripe_id {subscription_id}")
                        response = supabase.table("subscriptions").update(update_data).eq("id", sub_id).execute()
                        logger.info(f"Updated subscription: {response.data}")
                    
                    # We've successfully updated by stripe_id, so return early
                    return
            except Exception as e:
                logger.error(f"Error updating subscription by stripe_id: {str(e)}")
            
            # If we get here, we didn't find a matching subscription by stripe_id
            # Try to find by customer_id and user_id
            response = None
            customer_id = subscription.get('customer')
            
            if customer_id:
                try:
                    # Get user_id from customer_id
                    customer_response = supabase.table("stripe_customers").select("user_id").eq("customer_id", customer_id).execute()
                    if customer_response.data and len(customer_response.data) > 0:
                        user_id = customer_response.data[0].get('user_id')
                        if user_id:
                            # Look for existing active subscriptions for this user
                            existing_subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
                            
                            if existing_subs.data and len(existing_subs.data) > 0:
                                # User has active subscriptions, update them
                                update_data = {"status": db_status}
                                if end_date:
                                    update_data["end_date"] = end_date
                                
                                # Also update stripe_id if not set
                                for existing_sub in existing_subs.data:
                                    sub_id = existing_sub.get('id')
                                    sub_update_data = update_data.copy()
                                    
                                    # Add stripe_id if missing
                                    if not existing_sub.get('stripe_id'):
                                        sub_update_data["stripe_id"] = subscription_id
                                    
                                    logger.info(f"Updating existing subscription {sub_id} for user {user_id}")
                                    response = supabase.table("subscriptions").update(sub_update_data).eq("id", sub_id).execute()
                                    logger.info(f"Updated subscription: {response.data}")
                                
                                # We've updated existing subscriptions, so return early
                                return
                            elif db_status == "active" and not cancel_at_period_end:
                                # No active subscriptions but status is active and not canceling
                                # Create new subscription
                                try:
                                    import uuid
                                    from datetime import datetime, timedelta
                                    
                                    # Generate UUID for subscription
                                    db_sub_id = str(uuid.uuid4())
                                    
                                    # Get subscription details for timing
                                    start_date = datetime.now()
                                    end_date_ts = subscription.get('current_period_end')
                                    end_date_obj = datetime.fromtimestamp(end_date_ts) if end_date_ts else start_date + timedelta(days=30)
                                    
                                    # Create subscription
                                    sub_data = {
                                        "id": db_sub_id,
                                        "user_id": user_id,
                                        "status": "active", 
                                        "start_date": start_date.isoformat(),
                                        "end_date": end_date_obj.isoformat(),
                                        "created_at": start_date.isoformat(),
                                        "stripe_id": subscription_id
                                    }
                                    
                                    sub_result = supabase.table("subscriptions").insert(sub_data).execute()
                                    logger.info(f"Created new subscription for user {user_id}: {sub_result.data}")
                                    return
                                except Exception as e:
                                    logger.error(f"Error creating new subscription: {str(e)}")
                except Exception as e:
                    logger.error(f"Error getting user_id from customer: {str(e)}")
                
            # If we get here, we couldn't update any existing subscriptions
            # Log that we didn't find any subscriptions to update
            logger.warning(f"No existing subscriptions found to update for stripe_id {subscription_id}")
                
        except Exception as e:
            logger.error(f"Error updating subscription record: {str(e)}")
    
    def _handle_subscription_deleted(self, subscription: Dict[str, Any]) -> None:
        """Handle customer.subscription.deleted event."""
        try:
            # Extract subscription info
            subscription_id = subscription.get('id')
            
            logger.info(f"Processing subscription.deleted event: {subscription_id}")
            logger.debug(f"Full subscription data: {subscription}")
            
            if not subscription_id:
                logger.error("Subscription ID missing from delete event")
                return
                
            # Use the app-wide supabase client
            from app.database.supabase_client import supabase
            response = None  # Initialize response variable
            
            # First try to update by stripe_id directly
            try:
                update_data = {"status": "canceled"}
                logger.info(f"Looking for subscription with stripe_id {subscription_id}")
                response = supabase.table("subscriptions").update(update_data).eq("stripe_id", subscription_id).execute()
                
                if response.data and len(response.data) > 0:
                    logger.info(f"Subscription with stripe_id {subscription_id} marked as canceled: {response.data}")
                    return
            except Exception as e:
                logger.error(f"Error updating subscription by stripe_id: {str(e)}")
            
            # If that didn't work, try using customer information
            customer_id = subscription.get('customer')
            if customer_id:
                # Try to get the user_id associated with this customer
                try:
                    customer_response = supabase.table("stripe_customers").select("user_id").eq("customer_id", customer_id).execute()
                    if customer_response.data and len(customer_response.data) > 0:
                        user_id = customer_response.data[0].get('user_id')
                        if user_id:
                            # Update all active subscriptions for this user to canceled
                            update_data = {"status": "canceled"}
                                
                            logger.info(f"Marking subscriptions for user {user_id} as canceled")
                            response = supabase.table("subscriptions").update(update_data).eq("user_id", user_id).eq("status", "active").execute()
                            
                            if response.data and len(response.data) > 0:
                                logger.info(f"Subscriptions for user {user_id} marked as canceled: {response.data}")
                            else:
                                logger.warning(f"No active subscriptions found for user {user_id}")
                except Exception as e:
                    logger.error(f"Error getting user_id from customer: {str(e)}")
            
            if not response or not response.data:
                logger.warning(f"Could not find any subscriptions to cancel for Stripe subscription {subscription_id}")
                
        except Exception as e:
            logger.error(f"Error canceling subscription record: {str(e)}")
    
    def _handle_payment_succeeded(self, invoice: Dict[str, Any]) -> None:
        """Handle invoice.payment_succeeded event."""
        try:
            # Extract invoice info
            invoice_id = invoice.get('id')
            customer_id = invoice.get('customer')
            subscription_id = invoice.get('subscription')
            amount_paid = invoice.get('amount_paid', 0) / 100  # Convert from cents to dollars
            
            logger.info(f"Processing invoice.payment_succeeded event: {invoice_id}")
            logger.debug(f"Full invoice data: {invoice}")
            
            if not (invoice_id and customer_id):
                logger.error("Missing required invoice data (id or customer)")
                return
            
            # Check if we already processed this invoice
            from app.database.supabase_client import supabase
            subscription_id = invoice.get('subscription')
            
            # First check by transaction ID
            existing_payment = supabase.table("payments").select("id").eq("transaction_id", invoice_id).execute()
            if existing_payment.data and len(existing_payment.data) > 0:
                logger.info(f"Payment for invoice {invoice_id} already exists, skipping duplicate creation")
                return
                
            # If we have a subscription ID, check for existing payments and replace it
            # We WANT to replace "cs_test_" checkout session payments with proper invoice payments
            if subscription_id:
                existing_sub_payment = supabase.table("payments").select("*").eq("stripe_subscription_id", subscription_id).execute()
                if existing_sub_payment.data and len(existing_sub_payment.data) > 0:
                    # There's an existing payment for this subscription, but it's probably from the checkout session
                    payment_data = existing_sub_payment.data[0]
                    payment_id = payment_data.get('id')
                    existing_transaction_id = payment_data.get('transaction_id', '')
                    
                    # If it starts with cs_test_, it's a checkout session payment - replace it
                    if existing_transaction_id.startswith('cs_test_'):
                        logger.info(f"Found checkout session payment {payment_id} for subscription {subscription_id}, replacing with invoice payment")
                        # Delete the existing payment record
                        try:
                            delete_result = supabase.table("payments").delete().eq("id", payment_id).execute()
                            logger.info(f"Deleted checkout session payment: {delete_result.data}")
                        except Exception as e:
                            logger.error(f"Error deleting checkout session payment: {str(e)}")
                    else:
                        # It's a proper invoice payment, don't duplicate
                        logger.info(f"Payment for subscription {subscription_id} already exists with transaction_id {existing_transaction_id}, skipping duplicate creation")
                        return
                
            # Try to get the user ID
            user_id = None
            
            # Try to get from customer metadata
            try:
                customer = stripe.Customer.retrieve(customer_id)
                user_id = customer.get('metadata', {}).get('user_id')
                logger.info(f"User ID from customer metadata: {user_id}")
            except Exception as e:
                logger.error(f"Error retrieving customer: {str(e)}")
            
            # If still no user ID, try checking the subscription in our database using stripe_id
            if not user_id and subscription_id:
                try:
                    subscription_response = supabase.table("subscriptions").select("user_id").eq("stripe_id", subscription_id).execute()
                    if subscription_response.data and len(subscription_response.data) > 0:
                        user_id = subscription_response.data[0].get('user_id')
                        logger.info(f"User ID from subscription record: {user_id}")
                except Exception as e:
                    logger.error(f"Error looking up subscription in database: {str(e)}")
            
            # If still no user ID, try to get from stripe_customers table
            if not user_id and customer_id:
                try:
                    customer_response = supabase.table("stripe_customers").select("user_id").eq("customer_id", customer_id).execute()
                    if customer_response.data and len(customer_response.data) > 0:
                        user_id = customer_response.data[0].get('user_id')
                        logger.info(f"User ID from stripe_customers table: {user_id}")
                except Exception as e:
                    logger.error(f"Error looking up customer in database: {str(e)}")
            
            if not user_id:
                # Use customer ID as a fallback
                user_id = f"customer_{customer_id}"
                logger.warning(f"Using placeholder user ID: {user_id}")
                
            from datetime import datetime
            
            # Create payment record
            # Create a UUID for our payment
            import uuid
            payment_uuid = str(uuid.uuid4())
            
            # If user_id is not a valid UUID, find or create a proper user ID
            if user_id.startswith("customer_") or user_id == "unknown":
                # Try to find the proper user ID from the customer ID
                if customer_id:
                    try:
                        customer_response = supabase.table("stripe_customers").select("user_id").eq("customer_id", customer_id).execute()
                        if customer_response.data and len(customer_response.data) > 0:
                            user_id = customer_response.data[0].get('user_id')
                            logger.info(f"Found proper user_id from customer: {user_id}")
                    except Exception as e:
                        logger.error(f"Error getting user ID from customer: {str(e)}")
                        
                # If we still can't find a valid user ID, we should skip payment creation
                if user_id.startswith("customer_") or user_id == "unknown":
                    logger.warning(f"Cannot create payment with invalid user ID: {user_id}")
                    return
            
            payment_data = {
                "id": payment_uuid,
                "user_id": user_id,
                "amount": amount_paid,
                "status": "completed",
                "transaction_id": invoice_id,
                "created_at": datetime.now().isoformat(),
                "stripe_subscription_id": subscription_id  # Store the Stripe subscription ID
            }
            
            # For the subscription_id field, we need a UUID, not the Stripe ID
            # Try to find the corresponding subscription
            try:
                sub_check = supabase.table("subscriptions").select("id").eq("stripe_id", subscription_id).execute()
                if sub_check.data and len(sub_check.data) > 0:
                    # If we found a subscription with this stripe_id, link to it
                    payment_data["subscription_id"] = sub_check.data[0].get("id")
                    logger.info(f"Linked payment to subscription ID: {payment_data['subscription_id']}")
            except Exception as e:
                logger.error(f"Error finding subscription by stripe_id: {str(e)}")
                
            logger.info(f"Creating payment record for successful invoice: {payment_data}")
            payment_result = supabase.table("payments").insert(payment_data).execute()
            
            if payment_result.data:
                logger.info(f"Payment record created: {payment_result.data}")
                
                # If subscription ID is available, ensure the subscription is marked as active
                if subscription_id:
                    try:
                        # Check if subscription exists using stripe_id
                        sub_check = supabase.table("subscriptions").select("*").eq("stripe_id", subscription_id).execute()
                        
                        if sub_check.data and len(sub_check.data) > 0:
                            # Subscription exists, update it to active if needed
                            db_sub_id = sub_check.data[0].get('id')
                            logger.info(f"Ensuring subscription {db_sub_id} is marked as active")
                            supabase.table("subscriptions").update({"status": "active"}).eq("id", db_sub_id).execute()
                        else:
                            # Subscription doesn't exist, create it
                            logger.info(f"Subscription with stripe_id {subscription_id} not found, creating it")
                            
                            # Get subscription details from Stripe
                            try:
                                sub_data = stripe.Subscription.retrieve(subscription_id)
                                current_period_end = sub_data.get('current_period_end')
                                
                                # Convert timestamps to ISO format
                                from datetime import datetime, timedelta
                                start_date = datetime.now().isoformat()
                                end_date = datetime.fromtimestamp(current_period_end).isoformat() if current_period_end else (datetime.now() + timedelta(days=30)).isoformat()
                                
                                # Generate a proper UUID for the subscription
                                import uuid
                                db_subscription_id = str(uuid.uuid4())
                                
                                subscription_data = {
                                    "id": db_subscription_id,  # Use UUID as ID
                                    "user_id": user_id,
                                    "status": "active", 
                                    "start_date": start_date,
                                    "end_date": end_date,
                                    "created_at": start_date,
                                    "stripe_id": subscription_id  # Add the Stripe subscription ID
                                }
                                
                                sub_result = supabase.table("subscriptions").insert(subscription_data).execute()
                                logger.info(f"Backup subscription created from invoice: {sub_result.data}")
                                
                                # Update the payment to link to this subscription
                                try:
                                    payment_update = supabase.table("payments").update({"subscription_id": db_subscription_id}).eq("stripe_subscription_id", subscription_id).execute()
                                    logger.info(f"Updated payment to link to subscription: {payment_update.data}")
                                except Exception as e:
                                    logger.error(f"Error linking payment to subscription: {str(e)}")
                                
                            except Exception as e:
                                logger.error(f"Error creating backup subscription from invoice: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error checking/updating subscription status: {str(e)}")
            else:
                logger.error("Failed to create payment record for successful invoice")
                
        except Exception as e:
            logger.error(f"Error handling successful payment: {str(e)}")
    
    def _handle_payment_failed(self, invoice: Dict[str, Any]) -> None:
        """Handle invoice.payment_failed event."""
        try:
            # Extract invoice info
            invoice_id = invoice.get('id')
            customer_id = invoice.get('customer')
            subscription_id = invoice.get('subscription')
            amount = invoice.get('amount_due', 0) / 100  # Convert from cents to dollars
            
            logger.info(f"Processing invoice.payment_failed event: {invoice_id}")
            logger.debug(f"Full invoice data: {invoice}")
            
            if not (invoice_id and customer_id):
                logger.error("Missing required invoice data (id or customer)")
                return
                
            # Try to get the user ID
            user_id = None
            
            # Try to get from customer metadata
            try:
                customer = stripe.Customer.retrieve(customer_id)
                user_id = customer.get('metadata', {}).get('user_id')
                logger.info(f"User ID from customer metadata: {user_id}")
            except Exception as e:
                logger.error(f"Error retrieving customer: {str(e)}")
            
            # If still no user ID, try checking the subscription in our database
            if not user_id and subscription_id:
                try:
                    from app.database.supabase_client import supabase
                    subscription_response = supabase.table("subscriptions").select("user_id").eq("id", subscription_id).execute()
                    if subscription_response.data and len(subscription_response.data) > 0:
                        user_id = subscription_response.data[0].get('user_id')
                        logger.info(f"User ID from subscription record: {user_id}")
                except Exception as e:
                    logger.error(f"Error looking up subscription in database: {str(e)}")
            
            if not user_id:
                # Use customer ID as a fallback
                user_id = f"customer_{customer_id}"
                logger.warning(f"Using placeholder user ID: {user_id}")
                
            # Use the app-wide supabase client
            from app.database.supabase_client import supabase
            from datetime import datetime
            
            # Create payment record for the failed payment
            import uuid
            payment_id = str(uuid.uuid4())
            
            payment_data = {
                "id": payment_id,
                "user_id": user_id,
                "amount": amount,
                "status": "failed",
                "transaction_id": invoice_id,
                "created_at": datetime.now().isoformat()
            }
            
            # Add Stripe subscription ID if available
            if subscription_id:
                payment_data["stripe_subscription_id"] = subscription_id
                
                # Try to find a matching subscription in our database by stripe_id
                try:
                    sub_check = supabase.table("subscriptions").select("id").eq("stripe_id", subscription_id).execute()
                    if sub_check.data and len(sub_check.data) > 0:
                        # If we found a subscription with this stripe_id, link to it
                        payment_data["subscription_id"] = sub_check.data[0].get("id")
                except Exception as e:
                    logger.error(f"Error finding subscription by stripe_id: {str(e)}")
                
            logger.info(f"Creating payment record for failed invoice: {payment_data}")
            payment_result = supabase.table("payments").insert(payment_data).execute()
            
            if payment_result.data:
                logger.info(f"Failed payment record created: {payment_result.data}")
                
                # Don't update the subscription status here - Stripe will send a subscription.updated
                # event if the subscription status changes due to the failed payment
            else:
                logger.error("Failed to create payment record for failed invoice")
                
        except Exception as e:
            logger.error(f"Error handling failed payment: {str(e)}")


# Singleton instance
stripe_service = StripeService()