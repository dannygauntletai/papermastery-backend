-- Add stripe_id column to subscriptions table
ALTER TABLE subscriptions 
ADD COLUMN stripe_id VARCHAR(255);

-- Add stripe_subscription_id column to payments table
ALTER TABLE payments 
ADD COLUMN stripe_subscription_id VARCHAR(255);

-- Create an index on stripe_id for faster lookups
CREATE INDEX idx_subscriptions_stripe_id ON subscriptions(stripe_id);

-- Create an index on stripe_subscription_id for faster lookups
CREATE INDEX idx_payments_stripe_subscription_id ON payments(stripe_subscription_id);

-- Create a stripe_customers table to track customer IDs
CREATE TABLE IF NOT EXISTS stripe_customers (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  customer_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stripe_customers_user_id ON stripe_customers(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_customers_customer_id ON stripe_customers(customer_id);