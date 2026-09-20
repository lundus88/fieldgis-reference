# LD Global Commerce Readiness Gate v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: prevent LUNDUS DIGITAL SYSTEMS from treating worldwide enquiries as worldwide paid-order readiness while implementing the approved LD Global Transaction Principle.

## LD Global Transaction Principle

**Any qualified customer. Any supported market. One digital workflow.**

North Star:

**From any legitimate lead in the world to a completed paid digital service with minimal human friction.**

This is an operating objective, not an authorization to serve every jurisdiction. "Qualified customer" and "supported market" are mandatory gates. The principle must never bypass legal, tax, privacy, sanctions, payment, fraud, delivery, human-approval or Production controls.

## Commercial KPI chain

Visitor
→ Qualified Lead
→ Quotation
→ Payment
→ Delivery
→ Acceptance
→ Repeat / Referral

The funnel is measured end-to-end, but funnel progress does not grant hard-state authority. A lead may be globally accepted for enquiry while paid-order authority remains HOLD or MANUAL_REVIEW.

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
- A legitimate or qualified lead cannot override market-support evidence.
- A SUPPORTED market cannot bypass quotation, payment, acceptance or delivery controls.
- Production release remains human-gated.

## Initial rollout recommendation

Start with a small country matrix and widen only after real legal/payment/support evidence exists. Do not label "worldwide supported" until the matrix genuinely supports that statement.
