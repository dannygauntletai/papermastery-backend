# Project Requirements Document (PRD): Consulting System for ArXiv Mastery Platform

**Project Name:** Consulting System for PaperMastery  
**Domain:** papermastery.com
**Version:** 1.0  

---

## 1. Overview

### 1.1 Problem Statement
Users of the ArXiv Mastery Platform (PaperMastery) often seek a deeper understanding of academic papers beyond what automated tools like summaries and quizzes can offer. They want direct interaction with the researchers who authored these papers to ask questions, gain insights, and clarify complex concepts. However, connecting with researchers is difficult due to accessibility and logistical challenges.

### 1.2 Solution
The Consulting System will allow users to request and book consultations with researchers from the papers they are reading on PaperMastery. This feature will:
- Enable users to initiate outreach to researchers not yet on the platform through a subscription model.
- Allow direct booking of sessions with researchers already onboarded.
- Provide a seamless scheduling and session management system.
- Integrate with PaperMastery’s existing learning paths and gamification features.

---

## 2. Key Features

### 2.1 Researcher Outreach and Onboarding
- **Subscription Model:** Users pay a one-time subscription fee for unlimited researcher outreach requests.
  - This subscription also includes access to other premium features (to be defined).
  - No refunds are offered, as the subscription covers multiple benefits.
- **Outreach Process:**
  - PaperMastery scrapes researcher emails from arXiv (pending legal review).
  - Sends an invitation email to the researcher, outlining the benefits of joining (e.g., setting their own rates, earning 95%+ of session profits).
  - If the researcher accepts, they create a profile, set availability, and are verified (e.g., via email or institutional affiliation).
- **Handling Multiple Requests:**
  - If multiple users request the same researcher, the platform pools the requests and notifies all interested users once the researcher joins.

### 2.2 Session Booking
- **Direct Booking for Onboarded Researchers:**
  - Users can book sessions directly with researchers already on the platform without subscribing to the outreach feature.
  - Sessions are booked via an in-house scheduling system, with payments processed per session.
- **Session Fees:**
  - Researchers set their own session rates.
  - PaperMastery takes a small commission (e.g., 5%), with researchers receiving 95%+ of the session profits.
- **Scheduling System:**
  - Built in-house, integrated with Zoom for video sessions.
  - Users select time slots from the researcher’s availability and confirm bookings.

### 2.3 Integration with PaperMastery
- **Learning Path Enhancement:**
  - Consulting sessions can be suggested at key points in a user’s learning path.
  - Completing a session boosts the user’s mastery percentage or awards badges.
- **User Dashboard:**
  - Displays the status of outreach requests and booked sessions.
  - Integrates with the existing progress tracking and gamification features.

### 2.4 Legal and Compliance Considerations
- **Data Privacy:** Ensure compliance with GDPR and other privacy laws when scraping and using researcher emails.
- **Unsolicited Communication:** Comply with anti-spam laws (e.g., CAN-SPAM Act) by including opt-out options in outreach emails.
- **Payment Compliance:** Use a reputable payment processor to handle tax reporting and international payments.
- **Liability:** Implement terms of service to limit platform liability for session disputes.
- **Fraud Prevention:** Verify researcher identities to prevent fraudulent accounts.

---

## 3. User Journeys

### 3.1 Requesting a Consultation with a Researcher Not Yet on the Platform
1. User clicks "Consult with Researcher" on a paper’s page.
2. Subscribes to the consulting feature (one-time fee).
3. PaperMastery sends an outreach email to the researcher.
4. If the researcher joins, the user is notified and can book a session.
5. User selects a time slot, pays the session fee, and attends the Zoom session.

### 3.2 Booking a Session with an Onboarded Researcher
1. User clicks "Consult with Researcher" and sees the researcher is available.
2. User books a session directly by selecting a time slot and paying the fee.
3. Session occurs via Zoom at the scheduled time.

### 3.3 Multiple Users Requesting the Same Researcher
1. User A subscribes and requests outreach to Researcher X.
2. User B requests the same researcher and is notified that outreach is pending.
3. When Researcher X joins, both users are notified and can book sessions.

### 3.4 Researcher Declines or Does Not Respond
1. User subscribes and requests outreach.
2. If the researcher declines or doesn’t respond within a set timeframe, the user is notified.
3. No refund is issued, but the user can request other researchers.

### 3.5 Integration with Learning Paths
1. While progressing through a learning path, the platform suggests consulting the researcher.
2. User books a session (if onboarded) or subscribes to request outreach.
3. Completing the session enhances the user’s mastery percentage or awards badges.

---

## 4. Technical Requirements

### 4.1 Backend
- **Framework:** FastAPI (consistent with the original PRD).
- **Database:** Supabase (PostgreSQL).
- **Authentication:** Supabase Auth.
- **APIs:**
  - arXiv API for paper metadata and researcher emails.
  - Payment processor API (e.g., Stripe) for handling subscriptions and session fees.
  - Zoom API for managing video sessions.
- **Scheduling System:** Custom-built, integrated with researcher availability and user bookings.

### 4.2 Frontend
- **Framework:** React or Vue.js (consistent with the original PRD).
- **Components:**
  - Subscription page for consulting feature.
  - Outreach request form.
  - Session booking interface with calendar and payment options.
  - User dashboard with request and booking status.

### 4.3 AI and NLP Tools
- **Email Scraping:** Custom script to extract emails from arXiv (pending legal approval).
- **Outreach Automation:** Automated email system for sending invitations and follow-ups.

### 4.4 Legal and Compliance Tools
- **Consent Management:** Track researcher consent for data use.
- **Opt-Out Mechanism:** Include unsubscribe links in all outreach emails.
- **Tax Reporting:** Integrate with payment processor for automated tax documentation.

---

## 5. Success Metrics
- **Primary Metric:** Number of sessions booked (directly tied to revenue).
- **Secondary Metrics:**
  - Researcher onboarding rate.
  - User satisfaction with the consulting feature.
  - Impact on learning path completion rates.

---

## 6. Timeline and Milestones
- **Phase 1 (Weeks 1-4):** Legal review and compliance setup.
- **Phase 2 (Weeks 5-8):** Backend development (outreach, booking, scheduling).
- **Phase 3 (Weeks 9-12):** Frontend development (subscription, booking interfaces).
- **Phase 4 (Weeks 13-16):** Integration with PaperMastery’s learning paths and dashboard.
- **Phase 5 (Weeks 17-20):** Testing, user feedback, and refinements.

---

## 7. Risks and Mitigations
- **Legal Risks:** Consult with legal experts to ensure compliance with data privacy and anti-spam laws.
- **Researcher Non-Response:** Set clear expectations for users and provide alternative value through the subscription.
- **Technical Challenges:** Ensure robust integration with Zoom and the payment processor to avoid session disruptions.

---

This PRD provides a comprehensive outline for implementing the Consulting System within PaperMastery. It ensures alignment with the platform’s goals while addressing legal, technical, and user experience considerations.