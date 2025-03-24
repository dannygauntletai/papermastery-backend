# Backend Implementation Guide: Consultation Scheduling System

## Overview
This document outlines the backend requirements for supporting our consultation scheduling system. The frontend UI allows users to book time slots with researchers, submit questions, and process payments.

## Data Models

### Researcher
```typescript
interface Researcher {
  id: string;
  user_id?: string;  // ID of user account if researcher has one
  name: string;
  email: string;
  bio?: string;
  expertise: string[];  // e.g. ["machine learning", "physics"]
  achievements?: string[];
  rate: number;  // hourly rate in USD
  verified: boolean;
  avatar_url?: string;
  affiliation?: string;  // university/institution
  author?: boolean;  // if researcher is author of the paper
}
```

### TimeSlot
```typescript
interface TimeSlot {
  id: string;
  researcher_id: string;
  start_time: string;  // ISO datetime string
  end_time: string;    // ISO datetime string
  available: boolean;
  session_id?: string;  // populated if booked
}
```

### Session
```typescript
interface Session {
  id: string;
  user_id: string;
  researcher_id: string;
  time_slot_id: string;
  paper_id?: string;
  questions?: string;
  status: "scheduled" | "completed" | "canceled";
  payment_status: "pending" | "completed" | "failed" | "refunded";
  zoom_link?: string;
  created_at: string;
  updated_at: string;
}
```

## API Endpoints

### Researcher Endpoints
```
GET /api/researchers - List researchers with pagination
GET /api/researchers/:id - Get single researcher details
GET /api/researchers/search?query=... - Search researchers by name/expertise
```

### Time Slot Endpoints
```
GET /api/time-slots?researcher_id=:id&date=:date - Get researcher's available slots for a date
GET /api/time-slots/:id - Get details of a specific time slot
```

### Booking Endpoints
```
POST /api/sessions - Create a new booking
  Body: {
    time_slot_id: string;
    questions?: string;
    paper_id?: string;
  }

GET /api/sessions - Get user's booked sessions
GET /api/sessions/:id - Get details of a specific session
PATCH /api/sessions/:id/cancel - Cancel a booked session
```

### Payment Integration
```
POST /api/payment/intent - Create payment intent for Stripe
  Body: {
    session_id: string;
  }
  Response: {
    client_secret: string;
  }

POST /api/payment/confirm - Confirm payment completed
  Body: {
    session_id: string;
    payment_intent_id: string;
  }
```

## Implementation Details

### 1. Time Slot Availability

When retrieving time slots:
- Return all slots for the specified date and researcher
- Mark slots as `available: false` if already booked
- Include time in user's timezone where possible

```json
// Example response for GET /api/time-slots?researcher_id=123&date=2023-04-20
{
  "time_slots": [
    {
      "id": "slot1",
      "researcher_id": "123",
      "start_time": "2023-04-20T09:00:00Z",
      "end_time": "2023-04-20T10:00:00Z",
      "available": true
    },
    {
      "id": "slot2",
      "researcher_id": "123",
      "start_time": "2023-04-20T10:00:00Z",
      "end_time": "2023-04-20T11:00:00Z",
      "available": false
    }
  ]
}
```

### 2. Booking Process

The booking flow should:
1. Check slot availability before allowing booking
2. Create unpaid session record initially
3. Process payment through Stripe 
4. Update session status after successful payment
5. Send confirmation emails with Zoom links

Use a transaction to ensure slot isn't double-booked:
```sql
BEGIN TRANSACTION;
-- Check if slot is still available
SELECT available FROM time_slots WHERE id = :time_slot_id FOR UPDATE;
-- Mark slot as unavailable
UPDATE time_slots SET available = FALSE, session_id = :session_id WHERE id = :time_slot_id;
-- Create session record
INSERT INTO sessions (...) VALUES (...);
COMMIT;
```

### 3. Security Considerations

- Implement authorization to ensure users can only:
  - Book available slots
  - View/cancel their own sessions
  - See researcher details

- Validate all inputs, particularly:
  - Time slot IDs existence and availability
  - Date formats and ranges
  - Payment amounts matching researcher rates

### 4. Zoom Integration

- Automatically generate Zoom meetings for booked sessions:
  - Create meeting via Zoom API after successful payment
  - Include meeting link in session details and confirmation email
  - Consider calendar invitations (.ics files)

### 5. Researcher Availability Management

Implement a separate API for researchers to:
- Set recurring availability patterns
- Block specific dates/times
- View and manage their bookings

## Error Handling

All endpoints should return appropriate HTTP status codes:
- 400: Bad Request - Invalid input
- 401: Unauthorized - Authentication required
- 403: Forbidden - Insufficient permissions
- 404: Not Found - Resource doesn't exist
- 409: Conflict - Resource already booked/in use
- 500: Internal Server Error - Unexpected issues

Error responses should include:
```json
{
  "error": {
    "code": "SLOT_UNAVAILABLE",
    "message": "This time slot is no longer available",
    "details": {}
  }
}
```

## Database Considerations

Refer to the existing database schema in `consulting_database_schema.md` which includes tables for:
- researchers
- sessions
- payments
- reviews

Ensure proper indexing on frequently queried fields:
- researcher_id in time_slots table
- date fields for time-based queries
- user_id in sessions table

## Notifications

Implement notification triggers for:
- Booking confirmations
- Payment receipts
- Session reminders (24h and 1h before)
- Cancellation notifications 

## API Documentation

This section provides comprehensive documentation for all available consulting-related API endpoints.

### Authentication

All endpoints except webhooks require authentication. Authentication is handled through a JWT token that should be included in the Authorization header:

```
Authorization: Bearer <token>
```

The user information is retrieved using the `get_current_user` dependency.

### Base URL

All endpoints are prefixed with `/api/v1` followed by the specific route prefix:

- `/api/v1/consulting` - For consultation-related endpoints
- `/api/v1/auth` - For authentication-related endpoints
- `/api/v1/webhooks` - For webhook endpoints

### Response Format

Most endpoints return a standardized response format:

```json
{
  "success": true,
  "message": "Operation successful",
  "data": { ... }  // Response data
}
```

Error responses follow the standard HTTP status codes with a detail message:

```json
{
  "detail": "Error message"
}
```

### Researcher Endpoints

#### Get Researcher by ID

```
GET /api/v1/consulting/researchers/{researcher_id}
```

Retrieves a researcher's profile by their ID.

**Response:**
```json
{
  "success": true,
  "message": "Researcher retrieved successfully",
  "data": {
    "id": "uuid",
    "name": "John Smith",
    "email": "john.smith@university.edu",
    "bio": "Professor of AI...",
    "expertise": ["Machine Learning", "NLP"],
    "achievements": ["Award 1", "Publication 2"],
    "availability": {
      "monday": ["09:00-10:00", "14:00-15:00"],
      "tuesday": ["10:00-11:00", "15:00-16:00"]
    },
    "rate": 150.00,
    "verified": true,
    "user_id": "uuid",
    "created_at": "2023-06-01T12:00:00Z",
    "updated_at": "2023-06-02T12:00:00Z"
  }
}
```

#### Get Researcher by Paper ID

```
GET /api/v1/consulting/researchers/paper/{paper_id}
```

Retrieves the primary researcher associated with a paper.

**Response:** Same as the Get Researcher by ID endpoint.

#### Collect Researcher Data

```
POST /api/v1/consulting/researchers/collect
```

Collects researcher information from various sources like academic databases and social profiles.

**Request:**
```json
{
  "name": "John Smith",
  "affiliation": "Stanford University",
  "paper_title": "Deep Learning Applications in Computational Biology",
  "position": "Professor",
  "email": "john.smith@stanford.edu",
  "run_in_background": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Researcher data collection started for John Smith",
  "data": {
    "status": "processing",
    "researcher_id": "uuid"
  }
}
```

#### Collect Researchers by Institution

```
POST /api/v1/consulting/researchers/collect-by-institution
```

**Request:**
```json
{
  "institution": "Stanford University",
  "position": "Professor",
  "limit": 10
}
```

**Response:**
```json
{
  "success": true,
  "message": "Data collection for institution Stanford University started in background",
  "data": {
    "status": "background_started",
    "institution": "Stanford University",
    "limit": 10
  }
}
```

### Outreach Endpoints

#### Create Outreach Request

```
POST /api/v1/consulting/outreach
```

Creates a request to reach out to a researcher not yet on the platform.

**Request:**
```json
{
  "researcher_email": "researcher@university.edu",
  "paper_id": "uuid"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Outreach request created and email sent to researcher",
  "data": {
    "id": "uuid",
    "user_id": "uuid",
    "researcher_email": "researcher@university.edu",
    "paper_id": "uuid",
    "status": "pending",
    "created_at": "2023-06-01T12:00:00Z",
    "updated_at": "2023-06-01T12:00:00Z"
  }
}
```

### Session Endpoints

#### Create Session

```
POST /api/v1/consulting/sessions
```

Books a consultation session with a researcher.

**Request:**
```json
{
  "researcher_id": "uuid",
  "paper_id": "uuid",
  "start_time": "2023-06-10T14:00:00Z",
  "end_time": "2023-06-10T15:00:00Z"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Session created successfully",
  "data": {
    "id": "uuid",
    "user_id": "uuid",
    "researcher_id": "uuid",
    "paper_id": "uuid",
    "start_time": "2023-06-10T14:00:00Z",
    "end_time": "2023-06-10T15:00:00Z",
    "status": "scheduled",
    "zoom_link": "https://zoom.us/j/abcdefg",
    "created_at": "2023-06-01T12:00:00Z",
    "updated_at": "2023-06-01T12:00:00Z"
  }
}
```

#### Get User Sessions

```
GET /api/v1/consulting/sessions
```

Retrieves all sessions for the authenticated user.

**Response:**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "researcher_id": "uuid",
    "researcher_name": "John Smith",
    "paper_id": "uuid",
    "paper_title": "Deep Learning Applications",
    "start_time": "2023-06-10T14:00:00Z",
    "end_time": "2023-06-10T15:00:00Z",
    "status": "scheduled",
    "zoom_link": "https://zoom.us/j/abcdefg",
    "created_at": "2023-06-01T12:00:00Z",
    "updated_at": "2023-06-01T12:00:00Z"
  }
]
```

#### Get Session Details

```
GET /api/v1/consulting/sessions/{session_id}
```

Retrieves details for a specific session.

**Response:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "researcher_id": "uuid",
  "researcher_name": "John Smith",
  "paper_id": "uuid",
  "paper_title": "Deep Learning Applications",
  "start_time": "2023-06-10T14:00:00Z",
  "end_time": "2023-06-10T15:00:00Z",
  "status": "scheduled",
  "zoom_link": "https://zoom.us/j/abcdefg",
  "created_at": "2023-06-01T12:00:00Z",
  "updated_at": "2023-06-01T12:00:00Z"
}
```

#### Cancel Session

```
POST /api/v1/consulting/sessions/{session_id}/cancel
```

Cancels a scheduled session. Must be done at least 24 hours in advance.

**Response:**
```json
{
  "success": true,
  "message": "Session canceled successfully",
  "data": {
    "id": "uuid",
    "status": "canceled",
    "updated_at": "2023-06-02T12:00:00Z",
    "...": "..."
  }
}
```

#### Accept Session

```
POST /api/v1/consulting/sessions/{session_id}/accept
```

Allows a researcher to accept a session request.

**Response:**
```json
{
  "success": true,
  "message": "Session accepted successfully",
  "data": {
    "id": "uuid",
    "status": "scheduled",
    "updated_at": "2023-06-02T12:00:00Z",
    "...": "..."
  }
}
```

#### Get Researcher Availability

```
GET /api/v1/consulting/researchers/{researcher_id}/availability?date=2023-06-10
```

Retrieves available time slots for a specific researcher, optionally filtered by date.

**Response:**
```json
{
  "availability": {
    "2023-06-10": ["09:00-10:00", "14:00-15:00", "16:00-17:00"]
  }
}
```

### Payment Endpoints

#### Create Payment Intent

```
POST /api/v1/consulting/payments/intent
```

Creates a Stripe payment intent for a session or subscription.

**Request:**
```json
{
  "type": "session",
  "session_id": "uuid"
}
```

or

```json
{
  "type": "subscription"
}
```

**Response:**
```json
{
  "client_secret": "pi_abc123_secret_xyz456",
  "amount": 150.00,
  "type": "session"
}
```

#### Create Subscription

```
POST /api/v1/consulting/subscriptions
```

Creates a new consulting subscription for the current user.

**Response:**
```json
{
  "success": true,
  "message": "Subscription created successfully",
  "data": {
    "id": "uuid",
    "user_id": "uuid",
    "status": "active",
    "start_date": "2023-06-01T12:00:00Z",
    "end_date": null,
    "created_at": "2023-06-01T12:00:00Z"
  }
}
```

### Webhook Endpoints

#### Stripe Webhook

```
POST /api/v1/webhooks/stripe
```

Handles Stripe webhook events.

**Request:** Raw payload from Stripe with Stripe-Signature header
**Response:**
```json
{
  "status": "success",
  "message": "Processed payment_intent.succeeded event"
}
```

Supported events:
- `payment_intent.succeeded`: Update payment status and associated session/subscription
- `payment_intent.payment_failed`: Update payment status
- `customer.subscription.created`: Create or update subscription
- `customer.subscription.updated`: Update subscription
- `customer.subscription.deleted`: Update subscription status to canceled

### Auth Endpoints

#### Register Researcher

```
POST /api/v1/auth/register-researcher
```

Registers a new researcher using a token sent via email.

**Request:**
```json
{
  "name": "John Smith",
  "email": "john.smith@university.edu",
  "bio": "Professor of AI...",
  "expertise": ["Machine Learning", "NLP"],
  "achievements": ["Award 1", "Publication 2"],
  "availability": {
    "monday": ["09:00-10:00", "14:00-15:00"],
    "tuesday": ["10:00-11:00", "15:00-16:00"]
  },
  "rate": 150.00,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Researcher profile created successfully",
  "data": {
    "id": "uuid",
    "name": "John Smith",
    "email": "john.smith@university.edu",
    "...": "..."
  }
}
```

### Data Models

#### Researcher
```typescript
interface Researcher {
  id: string;
  name: string;
  email: string;
  bio?: string;
  expertise: string[];
  achievements?: string[];
  availability: {
    [day: string]: string[]  // e.g. { "monday": ["09:00-10:00", "14:00-15:00"] }
  };
  rate: number;
  verified: boolean;
  user_id?: string;
  created_at: string;
  updated_at?: string;
}
```

#### Session
```typescript
interface Session {
  id: string;
  user_id: string;
  researcher_id: string;
  paper_id?: string;
  start_time: string;  // ISO datetime string
  end_time: string;    // ISO datetime string
  status: "scheduled" | "completed" | "canceled";
  zoom_link?: string;
  created_at: string;
  updated_at?: string;
}
```

#### OutreachRequest
```typescript
interface OutreachRequest {
  id: string;
  user_id: string;
  researcher_email: string;
  paper_id?: string;
  status: "pending" | "accepted" | "declined" | "email_failed";
  created_at: string;
  updated_at?: string;
}
```

#### Subscription
```typescript
interface Subscription {
  id: string;
  user_id: string;
  status: "active" | "expired" | "canceled";
  start_date: string;
  end_date?: string;
  created_at: string;
}
```

#### Payment
```typescript
interface Payment {
  id: string;
  user_id: string;
  subscription_id?: string;
  session_id?: string;
  amount: number;
  status: "pending" | "completed" | "failed";
  transaction_id?: string;
  created_at: string;
}
``` 