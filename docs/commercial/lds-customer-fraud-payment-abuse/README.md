# LD Customer Fraud & Payment Abuse Protection v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: protect LUNDUS DIGITAL SYSTEMS from customer-side payment/dispute abuse without treating legitimate complaints or chargebacks as fraud by default.

## Principles

- Potential abuse signal != proven fraud.
- Consequential decisions remain human-controlled.
- Evidence is transactional/project evidence, not personality profiling.
- Legitimate disputes, defects and consumer rights remain valid review paths.
- Do not retaliate against a customer merely because a dispute exists.

## Core protections

1. Funding gate before BUILDING when the commercial agreement requires funded milestones.
2. Final-payment handover gate before unrestricted source/admin transfer when contractually agreed.
3. Authoritative order/payment channel only.
4. Human review for conflicting chargeback/refund claims.
5. Security fail-closed for credential/gate-bypass requests.
6. Immutable acceptance and delivery evidence.
7. Dispute Evidence Pack for chargeback/refund response.

## Dispute Evidence Pack

Recommended evidence references:
- approved quotation
- accepted SOW
- authoritative payment/provider reference
- artifact/version/Git SHA
- delivery timestamp and delivery acknowledgement
- UAT/acceptance evidence
- relevant written project communications

The pack supports fair human review. It does not automatically deny refunds or accuse the customer of fraud.

## Human-only actions

The module cannot autonomously:
- accuse a customer of fraud;
- deny a statutory refund/right;
- suspend or terminate a customer account;
- submit a chargeback rebuttal;
- contact banks/payment providers;
- begin legal action;
- retain money contrary to applicable law.

## Relationship to existing controls

Existing payment controls remain authoritative for signed webhook verification, amount/currency reconciliation, refund state and idempotency. This module adds merchant-side abuse detection and evidence preparation only.
