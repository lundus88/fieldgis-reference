# LD Global Commerce Readiness Gate v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: prevent LUNDUS DIGITAL SYSTEMS from treating worldwide enquiries as worldwide paid-order readiness.

## Core model

Every target country is classified:

- SUPPORTED
- MANUAL_REVIEW
- NOT_SUPPORTED

SUPPORTED is evidence-bound and human-approved. Unknown legal, tax, privacy, payment or operational conditions fail to MANUAL_REVIEW rather than being guessed.

## Required country dimensions

1. Country identity
2. Currency
3. Tax treatment
4. Contract jurisdiction
5. Privacy / personal-data handling
6. Data residency
7. Payment method
8. Support timezone
9. Builder capability
10. Delivery / UAT capability
11. Invoice / export requirements
12. Sanctions / restrictions check

## Current posture

- Technical factory readiness: CONDITIONAL
- Global enquiry: ALLOWED_MANUAL
- Global paid order: HOLD
- Public global checkout: HOLD

This gate does not activate payments, Production, public launch, tax registration, legal status or country support.

## Important separation

Global enquiry != global commerce.

A customer from another country may ask for a quotation while that country remains MANUAL_REVIEW.

Even a SUPPORTED country remains quote-only when public payment readiness is false.

## Evidence rules

- No country inherits Malaysia assumptions.
- No country support is inferred from language, currency similarity or customer location alone.
- Stale evidence cannot produce SUPPORTED.
- Legal/tax/privacy conclusions require appropriate current evidence and human approval.
- Builder support must be real for the requested software category.
- Production release remains human-gated.

## Initial rollout recommendation

Start with a small country matrix and widen only after real legal/payment/support evidence exists. Do not label "worldwide supported" until the matrix genuinely supports that statement.
