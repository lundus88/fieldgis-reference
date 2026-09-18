# LUNDUS DIGITAL SYSTEMS — Final Commercial Activation Gate

Status date: 2026-09-19
Overall status: HOLD
Authority: HUMAN-GATED
Scope: final pre-launch activation control; repository readiness is not Production activation authority.

## 1. Approved commercial proposition

Primary offer:
**Custom Digital Systems & Automation — Quotation-Led Implementation**

Status:
- OFFER_LOCKED: PASS
- quotation-led pricing approved
- customer-specific amount must be human-approved
- public fixed price is not required for launch

## 2. Protected-main commercial readiness sequence

The protected-main sequence has been completed through normal repository rules, formal review and exact-head CI.

Merged evidence:
- PR #277 master-compliance required-check scope -> `807b588dddd4bd1fd2c0c24e9b247a73ca895514`
- PR #275 PWA release-gate fix -> `af2673d1b9567b1aefed1877c3fc9b8b0419758c`
- PR #276 GIS preview public-readiness -> `8ffacb6b78d4107a4906d7960b3f048dfac8e2d9`
- PR #278 payment production-readiness RC -> `bef77304464b9e6480191090d8f7672ce203aad4`
- PR #280 fulfilment / receipt / close RC -> `d1fb85f69fe697848a8e654017d4b680bdb0b8ee`
- PR #281 customer notification RC -> `732bb7e2da9418ba9b74c08704bb3d3f033af6fe`
- PR #279 LUNDUS DIGITAL SYSTEMS commercial surface RC -> `724d293ecbd06ec191157d18ac3abb5a1fdcb2ff`
- PR #283 Commercial Golden Transaction dry-run -> `e2d52171503bd725c3638f0ac2fb60fe6d2e564e`
- PR #284 commercial sales / delivery pack -> `54530abc410cfccb1f5ea3219ec4ac79b4ee1901`
- PR #285 controlled launch operations pack -> `7a544c808b6e76491cc6ee50d8983fa35aa04316`
- PR #286 isolated commercial Preview deployment plan -> `bc8273a27d74dc489b2081aa2c62784d3673c799`

PR #282 is the remaining final activation-gate PR and must still pass its own protected-main review and exact-head checks before merge.

Do not bypass repository rulesets.

## 3. Separate LundusLead dependency

LundusLead public lead intake remains separate from this repository:
- repository: `lundus88/lundus-lead`
- PR #151: Ready for Review / unmerged
- LIVE_LEAD_INTAKE: HOLD
- no automatic quotation, pricing, payment or sale
- merge and Production activation must follow the LundusLead repository's own rules and human gate

The fieldgis-reference merge sequence does not authorize LundusLead Production changes.

## 4. Existing readiness evidence

Baseline PASS:
- support_intake
- incident_tracking
- production_rollback
- alerting_pipeline
- alerting_delivery
- payment_sandbox_e2e
- public_portal
- public_onboarding
- Golden Transaction dry-run
- protected-main commercial RC merge sequence

Still HOLD or not live-verified:
- LICENCE_READY
- LEGAL_TRUST_READY
- LIVE_LEAD_INTAKE
- live_billing
- Production commercial checkout
- live Commercial Golden Transaction
- Production payment-provider configuration
- commercial deployment-specific rollback evidence
- Preview deployment execution
- public launch

## 5. Mandatory business particulars before public transaction

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

## 6. Licence evidence gate

Current evidence classification:
- trade name: LUNDUS DIGITAL SYSTEMS — verified from user decision
- licence state: processing — USER-ATTESTED
- official approval/certificate evidence: not yet captured
- LICENCE_READY: HOLD
- LEGAL_TRUST_READY: HOLD

User attestation may document progress but cannot by itself set LICENCE_READY or LEGAL_TRUST_READY to PASS.

## 7. Preview deployment state

Preview plan is merged, but execution remains blocked pending a safe project-scoped mutation/authentication path.

Current state:
- PREVIEW_PLAN_MERGED: PASS
- project_creation_authorized: true
- preview_deployment_authorized: true
- production_promotion_authorized: false
- execution_state: blocked_by_tooling_and_auth_path

Preview constraints remain:
- dedicated isolated Vercel project
- no Production domain
- no Production secrets
- no customer data
- no live form
- no live checkout
- no search indexing
- no Production promotion

## 8. Production configuration gate

Before any Production commercial activation:
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

Repository merge does not apply these settings.

## 9. Controlled activation sequence from current state

1. Refresh PR #282 against current `main`; pass protected-main review and exact-head CI; merge only with explicit human approval.
2. Resolve LundusLead PR #151 under its own repository rules; keep LIVE_LEAD_INTAKE HOLD until separately authorized for Production.
3. Verify official business/licence evidence and all mandatory business particulars.
4. Update legal/trust surfaces with verified particulars and effective policy dates.
5. Establish a safe dedicated Preview mutation/authentication path and execute Preview only within the already-approved non-Production scope.
6. Verify Preview isolation, noindex/robots, mobile/static QA, rollback procedure and 5–10 invited-tester journey.
7. Verify Production payment, notification, WAF, origin and secret configuration without enabling public charging prematurely.
8. Run integration checks:
   - website -> lead intake
   - quotation -> customer-scoped offer
   - checkout creation
   - signed payment callback
   - manual fulfilment
   - receipt/invoice reference
   - controlled customer notification
   - close
9. Only after LICENCE_READY and LEGAL_TRUST_READY are PASS, perform one explicitly authorized controlled paid Commercial Golden Transaction.
10. Reconcile:
   - provider amount
   - backend order amount
   - signed webhook evidence
   - fulfilment evidence
   - receipt/invoice reference
   - notification delivery
   - support path
11. Set GOLDEN_TRANSACTION_PASS only from complete reconciled evidence.
12. Only then consider public payment activation under a separate human approval.

## 10. Commercial Golden Transaction acceptance

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
A dry-run PASS is not a live Golden Transaction PASS.

## 11. Launch status model

- LICENCE_READY: HOLD
- OFFER_LOCKED: PASS
- COMMERCIAL_SURFACE_READY: MERGED_RC / Production HOLD
- LEGAL_TRUST_READY: HOLD
- PAYMENT_PRODUCTION_READY: MERGED_RC / live activation HOLD
- GOLDEN_TRANSACTION_DRY_RUN: PASS
- GOLDEN_TRANSACTION_PASS: HOLD
- FULFILMENT_PASS: MERGED_RC / not live-verified
- NOTIFICATION_READY: MERGED_RC / not live-verified
- PREVIEW_PLAN_MERGED: PASS
- PREVIEW_EXECUTION: HOLD / blocked_by_tooling_and_auth_path
- LIVE_LEAD_INTAKE: HOLD
- SUPPORT_ROLLBACK_PASS: BASELINE_PASS / commercial live proof pending
- SECURITY_QA_PASS: RC_BASELINE_PASS / Production activation HOLD
- MEASUREMENT_READY: CONTRACT_READY / live evidence pending
- PUBLIC_PAYMENT_ACTIVATION: HOLD
- PUBLIC_LAUNCH: HOLD

## 12. Stop conditions

Do not activate public payment if any of these are true:
- licence/business authority not ready
- required legal/business particulars still placeholder or unverified
- LundusLead/public lead intake Production authority unresolved
- Production secrets/configuration unverified
- signed webhook path not validated in the intended environment
- amount mismatch exists
- payment reconciliation is uncertain
- fulfilment or receipt path cannot be completed
- customer notification evidence is unavailable where required
- rollback/support path is not usable
- Preview isolation is unresolved where Preview is required
- Golden Transaction has not passed

## 13. Human authority

This document does not authorize:
- protected-main merge
- Production deployment
- database migration application
- live billing activation
- live customer charging
- Production domain binding
- secret/configuration changes
- public launch
- widening of payment, fulfilment, notification or deployment authority

Those remain separately human-gated.
