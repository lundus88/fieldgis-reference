# LD Automated Commercial Document Lifecycle v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: orchestrate the commercial document flow on top of the existing payment, fulfilment and document ledgers.

## Canonical flow

QUOTATION APPROVED
→ INVOICE ISSUED
→ PAYMENT PENDING
→ PAYMENT RECONCILED
→ OFFICIAL RECEIPT ISSUED
→ MILESTONE FUNDED
→ HUMAN BUILD APPROVAL
→ BUILDING

## Authority boundaries

- quotation amount remains human-approved;
- invoice generation cannot change the approved amount;
- payment confirmation comes only from verified provider/backend evidence;
- a bank-transfer screenshot alone does not mark an order PAID;
- receipt issue requires reconciled PAID state;
- milestone funding does not itself authorize BUILDING;
- BUILDING remains human-gated where required;
- no automatic Production activation.

## Notifications

Lifecycle hooks may prepare/send, subject to the existing notification authority:
- invoice issued;
- payment confirmed;
- receipt issued;
- milestone funded.

Each notification must be idempotent and tied to the authoritative order/document state.

## Relationship to PR #298

PR #298 defines how Quotation, Invoice and Official Receipt look. This module defines when they may be issued and how they transition through the commercial workflow.

## Tax boundary

These lifecycle records are ordinary commercial documents. They must not claim Malaysian tax e-Invoice/MyInvois status unless a separately verified compliance workflow authorises it.
