# LD Global Demand Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: create a governed global acquisition and qualification layer for LUNDUS DIGITAL SYSTEMS without granting payment, Production, or country-support authority.

## Principle

**Any qualified customer. Any supported market. One digital workflow.**

North Star:

**From any legitimate lead in the world to a completed paid digital service with minimal human friction.**

## Scope

This engine covers:
- acquisition channels
- lead capture
- channel attribution
- lead qualification
- market-support precheck
- service-fit precheck
- consent / anti-spam guardrails
- funnel metrics
- handoff to commercial lifecycle

It does **not** authorize:
- country support
- payment
- quotation approval
- Production
- deployment
- legal/tax conclusions
- sanctions clearance
- customer acceptance

## Priority channels

P0:
- Google Search
- Clutch
- Upwork
- SEO / content

P1:
- LinkedIn
- Referral partners
- Affiliate partners

P2:
- Product Hunt for product/SaaS launches
- additional country-specific channels only after evidence review

## Canonical acquisition funnel

DISCOVERY
→ VISITOR
→ LEAD_CAPTURED
→ QUALIFICATION
→ QUALIFIED_LEAD
→ MARKET_SUPPORT_CHECK
→ SERVICE_FIT_CHECK
→ COMMERCIAL_HANDOFF

Commercial KPI mapping:

Visitor
→ Qualified Lead
→ Quotation
→ Payment
→ Delivery
→ Acceptance
→ Repeat / Referral

This engine owns only the acquisition-side states through QUALIFIED_LEAD and COMMERCIAL_HANDOFF.

## Qualification model

A lead is QUALIFIED only when:
1. contact method is valid
2. consent / lawful contact basis is recorded where required
3. source attribution exists
4. customer need is intelligible
5. requested service maps to an LD offer or paid discovery path
6. customer country is known enough for market-support evaluation
7. fraud / obvious abuse signals do not require HOLD
8. there is no explicit unsupported-market or prohibited-service condition

Qualification does not mean the customer may pay.

## Dependency gates

This engine depends on:
- PR #296 — LD Global Commerce Readiness Gate v1
- PR #317 — LD Integrated Customer Lifecycle Gate v1

Until those contracts are merged to main:
- country-support authority = NOT_SATISFIED
- paid-order authority = HOLD
- automatic checkout = HOLD
- commercial handoff may be prepared but must not be treated as paid-order readiness

## Channel strategy

### Google Search
Use high-intent problem keywords and dedicated English landing pages.

### Clutch
Use as a trust and discovery layer for buyers actively comparing service providers.

### Upwork
Use for early global project acquisition and proof-of-delivery, while keeping LD ownership of customer records and commercial evidence.

### SEO / Content
Create problem-led pages such as:
- AI automation for small business
- custom business workflow system
- internal operations portal
- client portal development
- website + automation package

### LinkedIn
Use for B2B founder/owner/manager targeting, authority content, and relationship-led outreach.

### Referral / Affiliate
Activate only with attribution, payout rules, fraud checks, and customer-consent boundaries.

### Product Hunt
Use for software/SaaS launch discovery; not as the default services acquisition channel.

## Governance invariants

- No channel may bypass lead qualification.
- No qualified lead may bypass market-support evaluation.
- No channel or campaign may imply worldwide paid-order support unless evidence says so.
- No automatic payment without downstream commerce authority.
- No purchased/spam list is accepted as a valid acquisition source.
- Consent and applicable anti-spam/privacy requirements must be respected.
- Attribution data informs marketing decisions but never grants commercial authority.
- Production and deployment remain HUMAN_ONLY.
- Unknown legal, tax, privacy, sanctions, payment, or market conditions fail closed to HOLD or MANUAL_REVIEW.

## Initial launch posture

- Global discovery: ALLOWED
- Global lead capture: ALLOWED_WITH_GUARDRAILS
- Global qualification: ALLOWED
- Global commercial handoff: CONDITIONAL
- Global paid order: HOLD
- Public global checkout: HOLD
- Production activation: NOT_AUTHORIZED
