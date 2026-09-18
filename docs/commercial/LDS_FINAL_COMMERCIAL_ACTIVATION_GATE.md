# LUNDUS DIGITAL SYSTEMS — Final Commercial Activation Gate

Status date: 2026-09-18
Overall status: HOLD
Authority: HUMAN-GATED
Scope: pre-launch activation control only

## 1. Approved commercial proposition

Primary offer:
**Custom Digital Systems & Automation — Quotation-Led Implementation**

Status:
- OFFER_LOCKED = YES
- quotation-led pricing approved
- customer-specific amount must be human-approved
- public fixed price is not required for launch

## 2. Technical RC status

### Ready at RC level
- PWA release-gate fix: PR #275
- GIS preview public-readiness: PR #276
- master-compliance required-check scope: PR #277
- payment production readiness: PR #278
- commercial surface: PR #279
- fulfilment / receipt / close: PR #280
- customer notification: PR #281
- LundusLead public lead intake: lundus88/lundus-lead PR #151

### Merge blocker
Protected-main requires formal approving review from a reviewer with write access.
Current designated reviewer: rnairing123.

Do not bypass repository rulesets.

## 3. Existing platform readiness evidence

Baseline PASS:
- support_intake
- incident_tracking
- production_rollback
- alerting_pipeline
- alerting_delivery
- payment_sandbox_e2e
- public_portal
- public_onboarding

Still HOLD:
- live_billing
- Production commercial checkout
- live Golden Transaction
- commercial deployment-specific rollback evidence

## 4. Mandatory business particulars before public transaction

The following values must be verified and inserted into the public commercial surface before LEGAL_TRUST_READY can become PASS:

- registered legal/business entity name
- registration/licence particulars applicable to the commercial activity
- final commercial domain
- official commercial email
- official commercial telephone
- official trade/business address
- official support / complaint channel
- effective date for Privacy Notice
- effective date for Terms of Service
- effective date for Refund & Cancellation Policy

No placeholder, inferred or historical address/contact may be substituted.

## 5. Production configuration gate

Before deployment:
- final commercial origin confirmed
- Turnstile site key configured
- Turnstile secret configured
- Turnstile hostname/action verified
- WAF / edge rate-limit rule evidenced
- LundusLead owner UUID verified
- Billplz production API secret verified
- Billplz collection ID verified
- Billplz X-signature secret verified
- Resend production API key verified
- Resend production sender verified
- Resend production webhook secret verified

Secrets must remain server-side.

## 6. Controlled activation sequence

1. Resolve protected-main review requirement.
2. Merge #277 first.
3. Re-run required checks on #275 / #276 / #278 / #279 / #280 / #281.
4. Merge only approved exact-head PRs.
5. Merge LundusLead #151 under its repository rules.
6. Verify business particulars and update legal/trust surfaces.
7. Verify licence readiness.
8. Configure Preview / controlled environment first.
9. Run integration checks:
   - website -> lead intake
   - quotation -> customer-scoped offer
   - checkout creation
   - signed payment callback
   - manual fulfilment
   - receipt/invoice reference
   - customer notification
   - close
10. Perform one controlled paid Golden Transaction.
11. Reconcile:
   - provider amount
   - backend order amount
   - webhook evidence
   - fulfilment evidence
   - receipt
   - notification delivery
   - support path
12. Only then consider public payment activation.

## 7. Commercial Golden Transaction acceptance

PASS requires evidence for one real controlled transaction:

Visitor / invited customer
-> enquiry or approved quotation
-> customer account
-> customer_quote offer
-> server-authoritative amount
-> checkout
-> provider payment
-> signed webhook
-> paid order
-> controlled notification
-> AAL2 human fulfilment
-> receipt/invoice reference
-> customer delivery
-> order close
-> reconciliation

A browser redirect is not payment evidence.

## 8. Launch status model

- LICENCE_READY: HOLD
- OFFER_LOCKED: PASS
- COMMERCIAL_SURFACE_READY: RC_READY
- LEGAL_TRUST_READY: HOLD
- PAYMENT_PRODUCTION_READY: RC_READY / HOLD for live activation
- GOLDEN_TRANSACTION_PASS: HOLD
- FULFILMENT_PASS: RC_READY / not live-verified
- SUPPORT_ROLLBACK_PASS: BASELINE_PASS
- SECURITY_QA_PASS: RC_READY / protected-main merge pending
- MEASUREMENT_READY: CONTRACT_READY / live evidence pending

## 9. Stop conditions

Do not activate public payment if any of these are true:
- licence/business authority not ready
- required legal/business particulars still placeholder
- protected-main PRs not merged through normal rules
- Production secrets/configuration unverified
- signed webhook path not validated
- amount mismatch exists
- payment reconciliation is uncertain
- fulfilment or receipt path cannot be completed
- rollback/support path is not usable
- Golden Transaction has not passed

## 10. Human authority

This document does not authorize:
- protected-main merge
- Production deployment
- database migration application
- live billing activation
- live customer charging
- secret/configuration changes
- widening of payment, fulfilment, notification or deployment authority

Those remain separately human-gated.
