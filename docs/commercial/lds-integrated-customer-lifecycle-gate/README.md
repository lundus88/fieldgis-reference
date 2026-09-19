# LD Integrated Customer Lifecycle Gate v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: connect the existing LD commercial and delivery modules into one evidence-bound customer lifecycle without creating another source of truth.

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
→ Renewal or Exit

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

## Advisory inputs

Pricing Intelligence, Reusable Solution Catalog, Delivery Benchmark, Profitability/Capacity and Vendor Risk may inform decisions. They never authorize a hard lifecycle transition.

## Key rule

A smaller project may have fewer optional artifacts, but it cannot skip payment reconciliation, kickoff, QA, customer acceptance or delivery evidence.

Production release remains a separate HUMAN_ONLY authority.
