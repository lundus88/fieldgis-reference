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

The protected-main commercial RC, governance and Preview UX sequence has completed through normal repository rules, formal review and exact-head CI.

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
- PR #282 final commercial activation gate -> `b2b9a97a03a825404a0ebe571a1cbfcfea743c09`
- PR #287 Preview navigation/mobile UX fix -> `57d4fe20c89e6cffc94047e7f6f7b4da4f4f538f`

Do not bypass repository rulesets.

## 3. LundusLead dependency

LundusLead public lead-intake code is merged but Production activation remains separately gated:
- repository: `lundus88/lundus-lead`
- PR #151 merge commit: `210e7cd0457b53958cdf9a235c110e5f2d08979c`
- code/CI/review merge gate: PASS
- LIVE_LEAD_INTAKE: HOLD
- no automatic quotation, pricing, payment or sale
- no Production Cloudflare deployment or Production migration is authorized by the merge
- Production origin, Turnstile/WAF, owner binding and enable flag remain currentness-sensitive inputs

The fieldgis-reference merge sequence does not authorize LundusLead Production activation.

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
- Preview V4 deployment
- Preview V4 visual QA
- Preview V4 workflow QA

Still HOLD or not live-verified:
- LICENCE_READY
- LEGAL_TRUST_READY
- LIVE_LEAD_INTAKE
- live_billing
- Production commercial checkout
- live Commercial Golden Transaction
- Production payment-provider configuration
- commercial deployment-specific rollback evidence
- public payment activation
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
- official approval/certificate evidence: not yet captured in connected sources
- LICENCE_READY: HOLD
- LEGAL_TRUST_READY: HOLD

User attestation may document progress but cannot by itself set LICENCE_READY or LEGAL_TRUST_READY to PASS.

## 7. Preview deployment state

Preview execution is complete and verified within the approved isolated scope.

Current state:
- PREVIEW_PROJECT_CREATED: PASS
- PREVIEW_EXECUTION: PASS / V4 READY
- PREVIEW_V4_VISUAL_QA: PASS
- PREVIEW_V4_WORKFLOW_QA: PASS
- project: `lundus-digital-systems-preview`
- project id: `prj_9areW7U50izhbz8yNrXK2r1YcJ1F`
- V4 Preview deployment id: `dpl_F4rugJSSdfWMmUzb6T2ShGSRnZCJ`
- commercial surface source SHA: `57d4fe20c89e6cffc94047e7f6f7b4da4f4f538f`
- Vercel API target for V4: non-Production / `null`; CLI reported Preview
- Production aliases on V4: none
- Production promotion authorized: false

The dedicated project also contains one prior inert technical Production bootstrap used only to unlock Vercel Preview behavior. That bootstrap is not evidence of commercial Production readiness.

Preview constraints remain:
- no Production promotion
- no customer data
- no live form submission
- no live checkout
- no search indexing
- no commercial Production domain binding

## 8. Production configuration gate

Before any controlled Production commercial transaction:
- final commercial origin confirmed
- Turnstile site key configured
- Turnstile secret configured
- Turnstile hostname/action verified
- WAF / edge rate-limit rule evidenced
- LundusLead owner UUID verified
- LundusLead Production configuration fingerprint captured
- Billplz production API secret verified
- Billplz collection ID verified
- Billplz X-signature secret verified
- payment-provider Production configuration fingerprint captured
- Resend production API key verified
- Resend production sender verified
- Resend production webhook secret verified

Secrets must remain server-side.
Repository merge does not apply these settings.
Configuration existence is not activation authority.

## 9. Activation Snapshot Contract

Final public launch must consume one explicit, current, single-use Activation Snapshot.

Contract files:
- `docs/commercial/LDS_ACTIVATION_SNAPSHOT.json`
- `docs/commercial/check_activation_snapshot.py`

Current snapshot state:
- snapshot_status: HOLD_NOT_FORMED
- launch_authorized: false
- snapshot_id: null

The final snapshot must bind:
- exact commercial artifact / release SHA
- exact reviewed Preview deployment and artifact fingerprint
- formal review evidence
- current business/licence evidence identifiers and validity
- legal/trust policy versions
- support-channel evidence
- live lead-intake Production configuration fingerprint
- payment-provider Production configuration fingerprint
- live Golden Transaction and reconciliation evidence
- approving human
- approval timestamp
- expiry / revalidation rule
- single-use consumption state

Rule:
**Evidence existence is not activation authority.**

If any material input changes after a launch snapshot is formed, or any required evidence cannot be shown current at execution time, activation returns to HOLD and a fresh snapshot is required.

## 10. Controlled activation sequence from current state

1. Capture and verify official business/licence evidence.
2. Verify all mandatory business particulars and replace legal/trust placeholders with evidence-backed values and effective policy dates.
3. Verify Production lead-intake, WAF, Turnstile, payment and notification configuration; capture configuration fingerprints without enabling public charging.
4. Obtain separate explicit human authority for the minimum controlled Production configuration needed to perform one Golden Transaction; this authority is not public-launch authority.
5. Perform one controlled paid Commercial Golden Transaction only after LICENCE_READY and LEGAL_TRUST_READY are PASS.
6. Reconcile:
   - provider amount
   - backend order amount
   - signed webhook evidence
   - fulfilment evidence
   - receipt/invoice reference
   - notification delivery
   - support path
7. Set GOLDEN_TRANSACTION_PASS only from complete reconciled evidence.
8. Revalidate the exact commercial artifact, Preview evidence, licence evidence, legal/support versions, lead-intake configuration and payment-provider configuration.
9. Form a fresh single-use Activation Snapshot with every mandatory gate PASS and no blockers.
10. Obtain explicit human approval of that exact Activation Snapshot.
11. Public payment activation / public launch may proceed only by consuming that approved, unexpired snapshot.
12. Any material drift before consumption invalidates the snapshot and returns the launch decision to HOLD.

## 11. Commercial Golden Transaction acceptance

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

## 12. Launch status model

- LICENCE_READY: HOLD
- OFFER_LOCKED: PASS
- COMMERCIAL_SURFACE_READY: MERGED_RC / Preview QA PASS / Production HOLD
- LEGAL_TRUST_READY: HOLD
- PAYMENT_PRODUCTION_READY: MERGED_RC / live activation HOLD
- GOLDEN_TRANSACTION_DRY_RUN: PASS
- GOLDEN_TRANSACTION_PASS: HOLD
- FULFILMENT_PASS: MERGED_RC / not live-verified
- NOTIFICATION_READY: MERGED_RC / not live-verified
- PREVIEW_PLAN_MERGED: PASS
- PREVIEW_EXECUTION: PASS / V4 READY
- PREVIEW_V4_VISUAL_QA: PASS
- PREVIEW_V4_WORKFLOW_QA: PASS
- LIVE_LEAD_INTAKE: HOLD
- SUPPORT_ROLLBACK_PASS: BASELINE_PASS / commercial live proof pending
- SECURITY_QA_PASS: RC_BASELINE_PASS / Production activation HOLD
- MEASUREMENT_READY: CONTRACT_READY / live evidence pending
- ACTIVATION_SNAPSHOT: HOLD_NOT_FORMED
- PUBLIC_PAYMENT_ACTIVATION: HOLD
- PUBLIC_LAUNCH: HOLD

## 13. Stop conditions

Do not activate public payment if any of these are true:
- licence/business authority not ready
- required legal/business particulars still placeholder or unverified
- live lead-intake Production authority unresolved
- Production secrets/configuration unverified
- required configuration fingerprint missing or stale
- signed webhook path not validated in the intended environment
- amount mismatch exists
- payment reconciliation is uncertain
- fulfilment or receipt path cannot be completed
- customer notification evidence is unavailable where required
- rollback/support path is not usable
- Golden Transaction has not passed
- Activation Snapshot is missing, expired, already consumed or based on stale evidence
- exact release / Preview / configuration inputs differ from the approved snapshot

## 14. Human authority

This document does not authorize:
- protected-main merge
- Production deployment
- database migration application
- live lead-intake activation
- live billing activation
- live customer charging
- Production domain binding
- secret/configuration changes
- public launch
- widening of payment, fulfilment, notification or deployment authority

Those remain separately human-gated.
