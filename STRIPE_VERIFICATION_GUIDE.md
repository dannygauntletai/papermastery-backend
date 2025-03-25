# Stripe Integration Verification Guide

This guide will help you verify that your Stripe integration is working properly, including subscription creation, management, and cancellation.

## What to Check in the Logs

### 1. Successful Subscription Status Check

The logs show the backend correctly checking a user's subscription status:

```
- Checking subscription status for user fd61680a-32a2-4f22-a7a2-2e16cf89d6b0
- User has active subscription: id=9d19b944-454b-4d8b-8f35-fcc3d47fd96a
- API responds with 200 OK
```

### 2. Successful Subscription Cancellation

The logs demonstrate a complete cancellation flow:

```
- User requests cancellation for subscription
- Backend retrieves the subscription details from Supabase
- Backend retrieves the customer ID to verify ownership
- Stripe API call succeeds (response code 200)
- Stripe subscription is marked for cancellation at period end
- Supabase database is updated to reflect cancellation
- API responds with 200 OK
```

### 3. Webhook Processing

The logs show webhook events being properly handled:

```
- Webhook received for customer.subscription.updated event
- Webhook signature verification passes
- New active subscription record created in database
- End date properly maintained
```

## Manual Verification Steps

### 1. Subscription Status Check

1. **Check Active Subscriptions in Supabase**
   ```sql
   SELECT * FROM subscriptions 
   WHERE user_id = 'fd61680a-32a2-4f22-a7a2-2e16cf89d6b0' 
   AND status = 'active';
   ```
   - Verify there's an active subscription for the user
   - Note the end date which should match the subscription period

2. **Check Stripe Dashboard**
   - Log in to the [Stripe Dashboard](https://dashboard.stripe.com/)
   - Go to "Customers" and find the customer by ID (cus_S0JGSaJXIt7Vk1)
   - Verify the customer has an active subscription
   - Check that the subscription is correctly marked for cancellation at period end

### 2. Webhook Processing

1. **View Recent Webhook Events in Stripe**
   - In Stripe Dashboard, go to "Developers" > "Webhooks"
   - Click on "Recent events"
   - Find the `customer.subscription.updated` event
   - Verify it was sent successfully
   - Check that your endpoint returned a 200 OK response

2. **Test Webhook Events**
   - In Stripe Dashboard, go to "Developers" > "Webhooks"
   - Click on your webhook endpoint
   - Click "Send test webhook"
   - Select an event type (e.g., `customer.subscription.updated`)
   - Verify your logs show proper handling of the test event

### 3. Price Verification

1. **Check Price in Stripe Dashboard**
   - Go to "Products" > "Subscriptions"
   - Verify the price is set to $10.00/month

2. **Check Price in Frontend**
   - Navigate to any consulting page in your application
   - Click the subscription button
   - Verify the price displayed is $10.00/month

3. **Check Checkout Session**
   - Inspect the Stripe Checkout URL when clicking "Subscribe"
   - Verify it contains the correct price ID parameter

### 4. Test Complete Subscription Flow

1. **Create a Test Subscription**
   - Use a [Stripe test card](https://stripe.com/docs/testing#cards) (e.g., 4242 4242 4242 4242)
   - Complete checkout
   - Verify you're redirected to the correct page after payment
   - Check the application shows you have an active subscription

2. **Cancel the Subscription**
   - Go to the Dashboard
   - Click "Cancel Premium"
   - Complete the cancellation flow
   - Verify you see a success message
   - Check the application still shows you have an active subscription (until period end)

3. **Check Cancellation in Stripe**
   - Go to the Stripe Dashboard
   - Find your subscription
   - Verify it's marked as "Canceling" or "Scheduled for cancellation"

## Troubleshooting

### Common Issues

1. **Webhook Signature Verification Failed**
   - Check that `STRIPE_WEBHOOK_SECRET` environment variable is properly set
   - Verify the secret matches the one in Stripe Dashboard > Developers > Webhooks

2. **Subscription Not Found**
   - Check that `stripe_id` is being properly stored in your subscriptions table
   - Verify the correct Stripe API key is being used

3. **User ID Not Found in Metadata**
   - Make sure `user_id` is being included in the metadata when creating checkout sessions
   - Check that the customer record in `stripe_customers` table links to the correct user

4. **Multiple Active Subscriptions**
   - Run this query to find users with multiple active subscriptions:
   ```sql
   SELECT user_id, COUNT(*) FROM subscriptions 
   WHERE status = 'active' 
   GROUP BY user_id 
   HAVING COUNT(*) > 1;
   ```

### Stripe API Failure Investigation

If Stripe API calls fail:

1. Check API key validity
2. Examine full error logs for specific error codes
3. Verify rate limits haven't been exceeded
4. Confirm the object IDs being used exist and are accessible

## Production Checklist

Before deploying to production:

1. ✅ Ensure Stripe is in **live mode** with proper API keys
2. ✅ Configure proper success and cancellation URLs with production hostnames
3. ✅ Set up proper webhook endpoint URLs and secrets for production
4. ✅ Test complete subscription and cancellation flow with test cards
5. ✅ Verify price is set correctly ($10.00/month)
6. ✅ Ensure error handling is robust and user-friendly
7. ✅ Monitor logs for any unexpected behavior
8. ✅ Set up alerts for failed webhook deliveries or API errors

This guide should help ensure your Stripe integration is working as expected. The logs you've provided indicate that the basic functionality is working correctly, with proper subscription management and webhook handling.