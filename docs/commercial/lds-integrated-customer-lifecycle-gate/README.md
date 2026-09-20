# LD Integrated Customer Lifecycle Gate v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: connect the existing LD commercial and delivery modules into one evidence-bound customer lifecycle without creating another source of truth.

## LD Global Transaction Principle alignment

**Any qualified customer. Any supported market. One digital workflow.**

North Star:

**From any legitimate lead in the world to a completed paid digital service with minimal human friction.**

Commercial KPI chain:

Visitor
→ Qualified Lead
→ Quotation
→ Payment
→ Delivery
→ Acceptance
→ Repeat / Referral

The KPI chain is a measurement model, not a bypass around the canonical evidence-bound lifecycle below.

## Canonical flow

Assessment
→ Blueprint
→ Pricing Review
→ Human-approved Quotation
→ Payment Reconciliation
→ Kickoff
→ Build
→ QA
→ UAT / Customer Acceptance
→ Delivery
→ Support
→ Renewal / Repeat / Referral / Exit

## Funnel-to-lifecycle mapping

- VISITOR: acquisition signal only; no project authority
- QUALIFIED_LEAD: Assessment / Blueprint
- QUOTATION: Pricing Review + Human-approved Quotation
- PAYMENT: authoritative Payment Reconciliation
- DELIVERY: Kickoff → Build → QA → UAT → Delivery
- ACCEPTANCE: customer acceptance evidence
- REPEAT_OR_REFERRAL: Support / Renewal / Referral / Exit

A funnel stage may be counted only when the corresponding evidence exists. KPI progression must never authorize a hard lifecycle transition.

## Hard gates

Mandatory consequential gates:
- approved scope
- human-approved quotation
- authoritative payment reconciliation
- kickoff readiness + human kickoff approval
- QA evidence
- customer acceptance evidence
- delivery evidence

## Conditional gates

Only when relevant:
- Change Request when scope changes materially
- Support Plan when recurring support is selected
- Handover/Exit when the project closes or customer exits
- Renewal Review when plan expiry/expansion evidence exists
- Referral/Testimonial only after delivery and customer acceptance

## Advisory inputs

Pricing Intelligence, Reusable Solution Catalog, Delivery Benchmark, Profitability/Capacity and Vendor Risk may inform decisions. They never authorize a hard lifecycle transition.

## Key rule

A smaller project may have fewer optional artifacts, but it cannot skip payment reconciliation, kickoff, QA, customer acceptance or delivery evidence.

Production release remains a separate HUMAN_ONLY authority.
