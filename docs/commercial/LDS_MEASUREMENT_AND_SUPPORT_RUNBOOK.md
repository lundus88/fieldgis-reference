# Commercial Measurement Runbook

Status: CONTRACT_READY

The launch metric design favours authoritative transaction events over behavioural profiling.

## Primary metrics
1. Website-origin leads
   - source: LundusLead
   - filter: lead_source = website
   - status progression: new -> qualified -> quotation -> sale/closed as implemented by LL

2. Human-approved quotations/offers
   - source: private.commercial_offers after PR #278 is authorised/applied
   - offer_type = customer_quote
   - status = active/retired

3. Checkout attempts
   - source: private.payment_production_orders
   - purpose = commercial_order
   - status = pending/paid/failed/cancelled/refunded

4. Paid conversion
   - paid commercial orders / active customer quotations issued

5. Fulfilment
   - source: private.payment_production_fulfillment_events
   - status = fulfilled

6. Closed orders
   - source: private.commercial_order_closures after PR #280 is authorised/applied

7. Customer notification
   - source: private.notification_outbox
   - environment = production
   - template_key = payment_confirmed/order_fulfilled/order_closed

8. Support rate
   - source: public.support_requests

9. Refund/cancellation rate
   - source: private.payment_production_orders
   - status in refunded/cancelled

## Launch principle
Do not require persistent cross-page user profiling for the first commercial launch. Session-level page/CTA events are supplementary; authoritative business metrics come from lead, order, payment, fulfilment, close and support ledgers.

## Evidence rule
A metric is not considered operational until the underlying Production table/path has real transaction evidence.

MEASUREMENT_READY:
- contract/schema design: READY
- live transaction evidence: HOLD until Commercial Golden Transaction #1


---

# Commercial Support & Rollback Readiness

Status date: 2026-09-18

## Existing live readiness evidence
The VL launch-readiness ledger currently reports:
- support_intake: PASS
- incident_tracking: PASS
- production_rollback: PASS
- alerting_pipeline: PASS
- alerting_delivery: PASS

Alert delivery evidence includes a controlled production notification test and recipient inbox confirmation from 2026-08-29.

## Commercial interpretation
SUPPORT_ROLLBACK_PASS = BASELINE_PASS for platform capability.

This does **not** yet prove rollback for the specific LUNDUS DIGITAL SYSTEMS commercial website because that customer-facing deployment does not yet exist in Production.

## Required commercial-specific proof
Before public charging:
1. commercial surface has an immutable deployment/artifact identifier;
2. previous known-good deployment is known;
3. rollback/revert path is documented;
4. quote/payment endpoints can be disabled independently;
5. lead intake can be disabled via fail-closed flag;
6. Production billing can be disabled without taking down the informational website;
7. support path is visible to customer;
8. operational incident can be opened and linked to the commercial deployment.

## Emergency posture
If payment state is uncertain:
- stop new checkout;
- preserve informational/quotation surface where safe;
- route order to Manual Review;
- do not fulfil;
- reconcile provider/backend evidence.

If lead intake is under abuse:
- set PUBLIC_LEAD_INTAKE_ENABLED=false;
- preserve the static commercial site;
- use manual contact fallback only after the verified contact channel is published.

If customer notification fails:
- payment/order state remains authoritative;
- do not roll back a valid payment because email delivery failed;
- use notification reconciliation/manual resend procedure.
