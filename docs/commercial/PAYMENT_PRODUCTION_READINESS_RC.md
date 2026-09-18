# Commercial Payment Production Readiness RC

Status: REVIEW CANDIDATE ONLY
Date: 2026-09-18
Production deployment: NOT AUTHORISED
Live billing activation: BLOCKED

## Evidence before this RC
- payment sandbox E2E: PASS
- production payment orders: 0
- production payment webhook events: 0
- production fulfilment events: 0
- live_billing readiness: BLOCKED
- existing production-test path: RM1.00 controlled test only

## Gap closed by this RC
The existing RM1.00 production-test endpoint is not a customer-grade checkout surface.
This RC introduces a governed commercial payment contract:

1. Browser submits only an approved `offer_key`.
2. Server resolves price/currency from `private.commercial_offers`.
3. Client-supplied amount is never accepted.
4. Active authenticated customer account and accepted terms are required.
5. Commercial origin must exactly match `LUNDUS_COMMERCIAL_ORIGIN`.
6. Billplz callback is HMAC-verified.
7. Amount must match the persisted server-authoritative order.
8. Duplicate callbacks are idempotent.
9. Cancelled/refunded orders are not resurrected.
10. Payment confirmation and fulfilment are separate states.

## Required human/configuration gates before deployment
- business licence ready
- final commercial domain known
- final first offer + amount approved
- privacy/terms/refund pages ready
- Billplz production credentials verified
- `LUNDUS_COMMERCIAL_ORIGIN` configured
- migration reviewed
- edge functions reviewed
- exact-head CI PASS
- explicit Production deployment approval

## Required live proof before public charging
A controlled transaction must prove:
checkout creation -> customer payment -> signed callback -> paid order -> operator notification -> fulfilment -> receipt/invoice -> reconciliation.

Until that proof completes, `PAYMENT_PRODUCTION_READY = HOLD`.
