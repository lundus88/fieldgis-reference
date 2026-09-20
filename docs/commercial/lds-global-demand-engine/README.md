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

## LD Global Growth Flywheel

The acquisition funnel is strengthened by five compounding loops:

### 1. Demand Loop
Content → Search → Social → Brand Memory

Purpose: create future demand and make LD mentally available before a buyer is ready to purchase.

### 2. Capture Loop
High-intent Search / Clutch / Upwork / LinkedIn / SEO
→ Landing Page
→ Lead Capture
→ Qualification

Purpose: convert active demand into qualified opportunities.

### 3. Proof Loop
Project
→ Measurable Result
→ Case Study
→ Review / Testimonial
→ Trust
→ More Qualified Leads

No result may be published as a case study without evidence and customer-permission handling where required.

### 4. Referral Loop
Accepted Delivery
→ Satisfied Customer
→ Referral
→ New Qualified Lead
→ Verified Sale
→ Approved Reward / Service Credit

Referral rewards must be evidence-based, fraud-checked and must not be triggered merely by a lead submission.

### 5. Expansion Loop
Initial Service
→ Delivered Outcome
→ Identified Adjacent Need
→ New Scope / Quotation
→ Additional Service
→ Support / Renewal

Expansion never bypasses quotation, scope, payment or lifecycle controls.

## Marketing hook

Primary customer-facing proposition:

**Tell us the business problem. We build the digital system.**

Supporting categories:

Website · AI · Automation · Business Systems

This marketing hook does not promise that every problem, jurisdiction or service request can be accepted.

## LD Digital Business Check

A free diagnostic lead magnet may be used to identify operational friction before commercial handoff.

Proposed flow:

Visitor
→ Digital Business Check
→ Digital Efficiency Score
→ Priority Opportunity Areas
→ Recommended Next Actions
→ Get My LD System Plan
→ Qualification

The diagnostic:
- is advisory only
- does not diagnose legal, tax, accounting or regulated matters
- does not grant country-support authority
- does not create a quotation or payment obligation
- must identify the evidence used for its recommendations
- must not fabricate ROI or guaranteed savings

## Growth measurement

Track at minimum:
- qualified-lead rate by channel
- quotation rate from qualified leads
- paid conversion rate after downstream approval
- delivery acceptance rate
- referral rate from accepted deliveries
- repeat / expansion rate
- cost per qualified lead where spend exists
- evidence-backed case-study count

Optimize for qualified revenue and customer outcomes, not raw traffic or vanity metrics.


## P0 Trust & Proof Engine

Purpose: convert completed work into verifiable buyer confidence.

Every proof item must carry:
- project/problem category
- evidence source
- measurable outcome or clearly labeled qualitative outcome
- customer-permission state
- verification state
- publication state
- claim limitations

Allowed publication states:
- HOLD
- INTERNAL_ONLY
- PUBLISHABLE

A case study or testimonial is PUBLISHABLE only when required evidence exists and customer permission is valid where required.

Proof CTA pattern:
Problem → Solution → Evidence → Outcome → Build Something Similar

## P0 Buyer Confidence Center

The Buyer Confidence Center is the self-service trust layer for remote/global buyers.

Required topics:
- how LD works
- service scope and offer types
- pricing logic
- delivery stages
- UAT / customer acceptance
- ownership and handover
- security and data handling
- change requests
- support and maintenance
- payment process
- cancellation/refund rules where applicable
- FAQ and escalation path

Every answer must have a source/owner and review state. Unknown or unresolved claims must display as NEEDS_REVIEW rather than being guessed.

## P0 Productized Offer Architecture

LD should sell clear outcomes rather than vague technology hours.

Initial offer families:
- LD LAUNCH — website / digital presence foundation
- LD AUTOMATE — workflow and repetitive-process automation
- LD AI — AI-assisted business workflow or assistant
- LD SYSTEM — custom business system / portal / internal tool
- LD DISCOVERY — paid discovery when scope is not yet sufficiently defined

Each offer must define:
- ideal problem
- inclusions
- exclusions
- prerequisite information
- delivery evidence
- UAT / acceptance criteria
- support boundary
- pricing mode
- change-request trigger

Productized offers improve buying clarity but do not create automatic quotation or payment authority.
