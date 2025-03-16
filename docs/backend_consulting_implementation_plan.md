The backend plan consists of 100 steps across 11 sprints, focusing on building the consulting feature. The key update is the use of RocketReach instead of ResearchGate for fetching missing researcher emails, reflected in the data collection services (Sprints 2 and 3).

Sprint 1: Project Setup and Database Foundation (Steps 1-10)
Update requirements.txt with dependencies: zoomus, stripe, firecrawl, tavily, rocketreach, pydantic.
Add Redis to docker-compose.yml for caching.
Update render.yaml with env vars: ZOOM_API_KEY, STRIPE_SECRET_KEY, FIRECRAWL_API_KEY, TAVILY_API_KEY, ROCKETREACH_API_KEY.
Add env vars to .env.example.
Extend app/core/config.py for consulting settings.
Document schema in docs/database_schema.md.
Define Pydantic models in app/api/v1/models.py for all tables.
Update existing models (Paper, Progress, Query) with new fields.
Enhance app/database/supabase_client.py for CRUD operations.
Generate Alembic migrations in migrations/.
Sprint 2: Data Collection Services - Setup (Steps 11-20)
Create app/services/firecrawl_service.py to scrape profiles.
Input: Researcher name, affiliation.
Output: Bio, publications.
Create app/services/tavily_service.py to enrich data.
Input: Name, scraped data.
Output: Achievements.
Create app/services/rocketreach_service.py to fetch emails.
Input: Name, affiliation.
Output: Email.
Create app/services/data_collection_orchestrator.py.
Define Pydantic models for services.
Add error handling for API failures.
Set up logging in app/core/logger.py.
Configure Redis caching in app/core/cache.py.
Add background job in app/core/cron.py.
Test services with mock data.
Sprint 3: Data Collection Services - Integration (Steps 21-30)
Implement collect_researcher_data in orchestrator.
Sequence: Firecrawl → RocketReach (if email missing) → Tavily.
Store Firecrawl data in researchers.
Update with RocketReach emails.
Enrich with Tavily data.
Add POST /consulting/researchers/collect endpoint.
Validate requests with Pydantic.
Return Pydantic response.
Handle partial updates.
Deduplicate by email.
Log completions.
Sprint 4: Consulting API Endpoints (Steps 31-40)
Create app/api/v1/endpoints/consulting.py.
Implement GET /consulting/researchers/{paper_id} with Pydantic response.
Add is_subscribed to GET /users/me.
Implement POST /consulting/outreach.
Implement POST /consulting/sessions.
Implement GET /consulting/researchers/{researcher_id}/availability.
Implement POST /consulting/payments/intent.
Implement POST /subscriptions.
Set up Stripe webhooks in app/api/v1/endpoints/webhooks.py.
Update statuses via webhooks.
Sprint 5: Outreach and Notifications (Steps 41-50)
Enhance app/services/email_service.py.
Create app/templates/emails/outreach_request.j2.
Create app/templates/emails/session_request.j2.
Generate JWT for registration.
Send outreach emails.
Add retry logic for emails.
Log email activities.
Implement POST /auth/register-researcher.
Implement POST /consulting/sessions/{session_id}/accept.
Update researchers with user_id.
Sprint 6: Session Management (Steps 51-60)
Create app/services/session_service.py.
Implement session creation.
Validate against availability.
Add acceptance logic.
Generate Zoom links in app/services/zoom_service.py.
Store Zoom links.
Implement GET /consulting/sessions.
Add cancellation logic.
Handle rescheduling.
Update status post-session.
Sprint 7: Payment and Subscription Management (Steps 61-70)
Enhance app/services/payment_service.py.
Implement subscription logic.
Handle renewals/expirations.
Add per-session payments.
Manage retries.
Generate invoices.
Calculate taxes in app/services/tax_service.py.
Implement refunds.
Log transactions.
Add GET /payments.
Sprint 8: Review and Rating System (Steps 71-80)
Implement POST /consulting/reviews.
Validate reviews with Pydantic.
Update researcher ratings.
Implement GET /consulting/researchers/{researcher_id}/reviews.
Add moderation logic.
Handle disputes.
Log submissions.
Add analytics.
Notify researchers.
Restrict to completed sessions.
Sprint 9: Dashboard and Analytics (Steps 81-90)
Implement GET /dashboard/user.
Implement GET /dashboard/researcher.
Add session analytics.
Add subscription analytics.
Add payment analytics.
Add researcher metrics.
Add engagement metrics.
Add export endpoints.
Cache with Redis.
Ensure role-based dashboards.
Sprint 10: Security and Compliance (Steps 91-100)
Encrypt sensitive fields.
Implement consent management.
Add email opt-out.
Generate terms of service.
Handle GDPR features.
Add audit trails.
Implement rate limiting.
Add IP whitelisting.
Handle timeouts.
Enforce password policies.