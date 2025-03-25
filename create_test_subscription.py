#!/usr/bin/env python3
"""
Script to create a test subscription in the database for testing purposes.
"""
import os
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
import argparse

# Load environment variables
load_dotenv()

# Make sure we can import from our app
import sys
sys.path.append('.')

# Import our Supabase client
from app.database.supabase_client import supabase
from app.core.logger import get_logger

logger = get_logger(__name__)

def create_test_subscription(user_id, duration_days=30):
    """Creates a test subscription for the specified user."""
    # Generate UUIDs for the records
    subscription_id = str(uuid.uuid4())
    payment_id = str(uuid.uuid4())
    stripe_subscription_id = f"sub_test_{uuid.uuid4().hex[:8]}"
    transaction_id = f"tx_test_{uuid.uuid4().hex[:8]}"
    
    # Calculate dates
    start_date = datetime.now()
    end_date = start_date + timedelta(days=duration_days)
    
    # Create subscription record
    subscription_data = {
        "id": subscription_id,
        "stripe_id": stripe_subscription_id,
        "user_id": user_id,
        "status": "active",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "created_at": start_date.isoformat()
    }
    
    # Create payment record
    payment_data = {
        "id": payment_id,
        "user_id": user_id,
        "amount": 19.99,
        "status": "completed",
        "transaction_id": transaction_id,
        "stripe_subscription_id": stripe_subscription_id,
        "created_at": start_date.isoformat()
    }
    
    print(f"Creating test subscription for user {user_id}")
    print(f"Subscription data: {subscription_data}")
    print(f"Payment data: {payment_data}")
    
    try:
        # Insert subscription record
        sub_result = supabase.table("subscriptions").insert(subscription_data).execute()
        print(f"✅ Subscription record created: {sub_result.data}")
        
        # Insert payment record
        payment_result = supabase.table("payments").insert(payment_data).execute()
        print(f"✅ Payment record created: {payment_result.data}")
        
        print(f"\n✅ Success! User {user_id} now has an active subscription")
        return True
    except Exception as e:
        print(f"❌ Error creating test subscription: {str(e)}")
        return False

def check_subscription_status(user_id):
    """Check if the user has an active subscription."""
    try:
        # Query for active subscriptions for this user
        response = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
        subscriptions = response.data
        has_subscription = len(subscriptions) > 0
        
        if has_subscription:
            print(f"✅ User {user_id} has active subscription: {subscriptions[0]}")
        else:
            # Log all subscriptions regardless of status
            all_subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
            if all_subs.data:
                print(f"❌ User {user_id} has {len(all_subs.data)} non-active subscriptions: {all_subs.data}")
            else:
                print(f"❌ User {user_id} has no subscriptions in database")
        
        return has_subscription
    except Exception as e:
        print(f"❌ Error checking subscription status: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a test subscription for a user")
    parser.add_argument("user_id", help="The UUID of the user to create a subscription for")
    parser.add_argument("--duration", type=int, default=30, help="Duration of subscription in days (default: 30)")
    parser.add_argument("--check-only", action="store_true", help="Only check subscription status, don't create one")
    
    args = parser.parse_args()
    
    if args.check_only:
        check_subscription_status(args.user_id)
    else:
        create_result = create_test_subscription(args.user_id, args.duration)
        if create_result:
            # Verify it worked
            check_subscription_status(args.user_id)