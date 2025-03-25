# Supabase Migrations

This directory contains SQL migration files for Supabase database schema changes.

## Migration Files

1. `add_stripe_id_to_subscriptions.sql` - Adds `stripe_id` column to the subscriptions table and `stripe_subscription_id` to the payments table to properly handle Stripe's non-UUID subscription IDs.

## How to Apply Migrations

1. Log into the Supabase dashboard for your project
2. Navigate to the "SQL Editor" section
3. Click "New Query"
4. Copy and paste the contents of the migration file you want to run
5. Review the SQL changes to ensure they're appropriate for your environment
6. Click "Run" to execute the migration

## Important Notes

- These migrations should be applied in order
- Always make a backup of your database before running migrations
- Test migrations on a development environment before applying to production
- The Stripe webhook handlers have been updated to work with these schema changes