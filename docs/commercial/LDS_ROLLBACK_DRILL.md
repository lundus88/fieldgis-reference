# LUNDUS DIGITAL SYSTEMS — Rollback Drill

Status: PRE-LAUNCH DRILL
Purpose: prove that failure in one commercial subsystem does not force unsafe continuation.

## Scenario A — Payment state uncertain
Trigger:
- provider says paid but backend state is missing/uncertain;
- amount mismatch;
- signature verification fails.

Action:
1. Disable new checkout.
2. Preserve informational/quotation pages if safe.
3. Mark affected order Manual Review.
4. Do not fulfil.
5. Reconcile provider bill ID, amount and signed callback.
6. Re-enable only after evidence is consistent.

PASS condition:
No fulfilment occurs while payment evidence is uncertain.

## Scenario B — Lead intake abuse
Trigger:
- abnormal submission volume;
- Turnstile/hostname mismatch;
- WAF/rate-limit alert.

Action:
1. Set PUBLIC_LEAD_INTAKE_ENABLED=false.
2. Preserve static website.
3. Keep direct CRM/database writes inaccessible to browser.
4. Restore only after origin, Turnstile and rate-limit controls are verified.

PASS condition:
Static site remains usable while public lead intake is disabled.

## Scenario C — Customer notification failure
Trigger:
- Resend API failure;
- signed webhook missing;
- delivery/bounce issue.

Action:
1. Keep payment/order state authoritative.
2. Do not reverse valid payment solely because email failed.
3. Reconcile notification outbox/provider evidence.
4. Use controlled manual resend if authorised.

PASS condition:
Notification failure cannot corrupt payment or fulfilment state.

## Scenario D — Commercial website deployment defect
Trigger:
- broken critical page;
- wrong legal/contact details;
- checkout exposed before gate;
- severe mobile/navigation defect.

Action:
1. Disable checkout/lead intake as appropriate.
2. Roll back to last known-good immutable deployment.
3. Confirm Home / Services / Contact / legal pages.
4. Re-run smoke test before re-opening.

PASS condition:
Known-good surface can be restored without mutating customer/payment data.

## Scenario E — Licence/legal gate regression
Trigger:
- licence expires/revoked/not yet effective;
- business particulars become invalid;
- policy disclosure is incomplete.

Action:
1. Disable public payment immediately.
2. Keep only safe informational/quotation content if permitted.
3. Set LICENCE_READY or LEGAL_TRUST_READY back to HOLD.
4. Re-open payment only after official evidence is restored.

PASS condition:
Commercial charging cannot continue while legal authority is HOLD.

## Drill evidence
Record:
- scenario;
- trigger;
- operator;
- exact release/deployment;
- disable action;
- rollback action;
- verification result;
- time started/completed;
- unresolved risks.

This drill is documentation/QA only until a real commercial deployment exists.
