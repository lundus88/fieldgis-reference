# LUNDUS DIGITAL SYSTEMS — Launch-Day Operator Checklist

Status: HUMAN-GATED
Public payment activation: HOLD until all mandatory gates PASS.

## T-60 minutes
- Confirm exact approved release commit.
- Confirm formal PR approvals and required checks.
- Confirm licence evidence is official and LICENCE_READY = PASS.
- Confirm registered business particulars are inserted and verified.
- Confirm Privacy / Terms / Refund effective dates.
- Confirm final commercial domain.
- Confirm official email, phone, trade address and support/complaint channel.
- Confirm Production secrets/configuration are present server-side only.
- Confirm previous known-good deployment / rollback target.

## T-30 minutes
- Confirm lead intake origin, Turnstile hostname/action and rate-limit configuration.
- Confirm Billplz Production credentials, Collection ID and X-signature secret.
- Confirm Resend Production sender and webhook secret.
- Confirm checkout remains disabled until explicit activation step.
- Confirm informational website can remain available if payment is disabled.

## T-15 minutes
Run smoke tests:
1. Home 200.
2. Services 200.
3. Contact 200.
4. Privacy / Terms / Refund / Maklumat Urus Niaga 200.
5. Lead submission path in controlled mode.
6. Customer-specific quotation/offer lookup.
7. Checkout creation in controlled mode only.
8. Signed webhook verification path.
9. Manual fulfilment path.
10. Receipt/invoice reference path.
11. Notification path.
12. Support path.
13. Rollback switch/path.

## Human GO gate
The operator must explicitly verify:
- LICENCE_READY = PASS
- OFFER_LOCKED = PASS
- COMMERCIAL_SURFACE_READY = PASS
- LEGAL_TRUST_READY = PASS
- PAYMENT_PRODUCTION_READY = PASS
- FULFILMENT_PASS = PASS
- SUPPORT_ROLLBACK_PASS = PASS
- SECURITY_QA_PASS = PASS
- MEASUREMENT_READY = PASS

If any item is HOLD, stop.

## Controlled Golden Transaction
Run one invited-customer transaction only:
Quotation
-> customer account
-> customer-scoped offer
-> exact server amount
-> checkout
-> real provider payment
-> signed callback
-> paid order
-> controlled notification
-> AAL2 human fulfilment
-> receipt/invoice reference
-> delivery evidence
-> close
-> reconciliation

## Reconciliation
Verify:
- provider amount = backend order amount;
- provider bill ID matches order;
- signed callback stored;
- duplicate callback is idempotent;
- fulfilment was not automatic;
- receipt exists;
- notification evidence exists;
- order close evidence exists;
- support channel works.

## GO after Golden Transaction
Public payment may only be considered after the controlled transaction is fully reconciled and no P0 blocker remains.

A browser redirect is never payment evidence.
