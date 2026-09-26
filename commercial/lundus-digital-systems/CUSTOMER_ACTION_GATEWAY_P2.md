# LD Client Portal P2 — Customer Action Gateway

Status: DEVELOPMENT / NON-PRODUCTION

## Purpose

Close the gap between the read-only Client Portal and existing authoritative customer workflows without creating a second source of truth.

P2 supports two bounded customer-originated actions:

1. Request Change
2. UAT Accept

The portal UI remains disabled until this backend gateway has passed CI, review and a separate runtime activation decision.

## Reuse architecture

Client Portal
→ Customer Action Gateway
→ Customer Organization & IAM Boundary Engine
→ existing authoritative workflow owner

For Request Change:

Customer Action Gateway
→ Change Request & Scope Ledger

For UAT Accept:

Customer Action Gateway
→ Integrated Customer Lifecycle Gate
→ QA_PASSED → CUSTOMER_ACCEPTED

## Authority

The gateway may validate and prepare an evidence-backed handoff. It does not commit authoritative state.

It has no authority to:

- alter approved scope directly;
- alter quotation or invoice;
- approve pricing;
- charge or refund;
- mark payment reconciled;
- mark QA passed;
- deploy Production;
- perform destructive Production actions;
- widen privileges.

## Idempotency

Every consequential customer action requires an idempotency key.

A consumed key returns IDEMPOTENT_REPLAY and creates no second mutation.

## Tenant isolation

Customer actions reuse Customer Organization & IAM. Cross-organization requests fail closed.

Project mutation actions require an existing role with manage_project authority. The gateway does not invent new IAM roles or permissions.

## Source-of-truth rule

The gateway is an adapter only.

Request Change prepares a REQUESTED intake for the existing Change Request & Scope Ledger.

UAT Accept asks the existing Integrated Customer Lifecycle Gate to validate the QA_PASSED → CUSTOMER_ACCEPTED transition and returns a handoff receipt.

In both cases source_truth_mutated remains false inside the gateway.
