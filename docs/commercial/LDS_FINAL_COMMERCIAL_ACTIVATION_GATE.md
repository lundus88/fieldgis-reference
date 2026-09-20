# LUNDUS DIGITAL SYSTEMS — Final Commercial Activation Gate

Status date: 2026-09-20
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
- final commercial domain ownership verification: `lundusdigital.com`
- BUSINESS_REGISTRATION_READY
- LICENCE_READY

Still HOLD or not live-verified:
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

Verified from official SSM evidence:
- registered business name: LUNDUS DIGITAL SYSTEMS
- registration number: 202603248473 (003891235-V)
- legal form: sole proprietorship
- registration status: ACTIVE
- registration validity through 18/09/2027
- registered activity scope covers the current LD software / SaaS / AI / automation / IT consultancy offer

Verified commercial channels:
- official commercial email: hello@lundusdigital.com — PASS
- official support / complaint channel: support@lundusdigital.com — PASS_INBOUND

Approved effective policy versions:
- Privacy Notice v1.0 — effective 20 September 2026
- Terms of Service v1.0 — effective 20 September 2026
- Refund & Cancellation Policy v1.0 — effective 20 September 2026

Verified from official SSM evidence but still approval-gated for public commercial use:
- a telephone value is present in SSM Form A; exact value remains redacted in this public repository and is not yet approved as the LD public commercial phone
- the principal business address is verified from SSM evidence; exact value remains redacted and public display is not yet approved

The trade address overlaps owner residential information in the official evidence. Exact address and telephone values are intentionally not persisted in this public repository until explicit public-use/publication approval. Evidence existence is not publication authority.

## 6. Business registration / licence evidence gate

Current evidence classification:
- registered business name: LUNDUS DIGITAL SYSTEMS — OFFICIAL SSM EVIDENCE
- registration number: 202603248473 (003891235-V) — OFFICIAL SSM EVIDENCE
- legal form: SOLE PROPRIETORSHIP — OFFICIAL SSM EVIDENCE
- registered from: 19/09/2026
- registration valid until: 18/09/2027
- registration status: ACTIVE
- registered commercial activities cover the current LD offer
- BUSINESS_REGISTRATION_READY: PASS
- LICENCE_READY: PASS
- LEGAL_TRUST_READY: HOLD

Interpretation:
`LICENCE_READY` is retained for compatibility with the existing launch model. PASS here means official business-registration evidence applicable to LD's commercial scope has been verified. It does **not** claim a separate sector-specific licence, certification, statutory professional approval, or government endorsement.

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

Preview constraints remain:
- no Production promotion
- no customer data
- no live form submission
- no live checkout
- no search indexing
- no commercial Production domain binding

## 8. Production configuration gate

Current domain/email readiness:
- FINAL_COMMERCIAL_DOMAIN: PASS / `lundusdigital.com`
- DOMAIN_OWNERSHIP_VERIFIED: PASS
- DNS_PRODUCTION_BINDING: HOLD
- EMAIL_PROVIDER_SELECTED: PASS / Zoho Mail Lite 10 GB
- EMAIL_SUBSCRIPTION_ACTIVE: PASS / Zoho Mail Lite 10 GB / renewal 19/09/2027
- EMAIL_DNS_AUTHENTICATION: PASS
- OFFICIAL_COMMERCIAL_EMAIL: PASS / `hello@lundusdigital.com`
- SUPPORT_COMPLAINT_CHANNEL: PASS_INBOUND / `support@lundusdigital.com`
- email provider: Zoho Mail / Mail Lite 10 GB — SELECTED, subscription PURCHASED / 1-year term / next renewal 19/09/2027
- mailbox architecture: 1 licensed mailbox `hello@lundusdigital.com`; verified inbound aliases `support@lundusdigital.com`, `billing@lundusdigital.com`, `dmarc@lundusdigital.com`
- transactional/system email remains on Resend
- DNS record mutation authorized: false
- Vercel Production domain binding authorized: false

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

## 10. Controlled activation sequence from current state

1. **COMPLETE:** capture and verify official business-registration/licence evidence.
2. Obtain explicit human approval to use the verified SSM telephone as the LD public commercial phone and to publish the verified trade address. Policy versions 1.0 are already approved effective 20 September 2026.
3. Verify Production lead-intake, WAF, Turnstile, payment and notification configuration; capture configuration fingerprints without enabling public charging.
4. Obtain separate explicit human authority for the minimum controlled Production configuration needed to perform one Golden Transaction; this authority is not public-launch authority.
5. Perform one controlled paid Commercial Golden Transaction only after LEGAL_TRUST_READY is PASS and all Production transaction prerequisites are current.
6. Reconcile provider amount, backend order amount, signed webhook, fulfilment, receipt/invoice, notification, support path and order close.
7. Set GOLDEN_TRANSACTION_PASS only from complete reconciled evidence.
8. Revalidate the exact commercial artifact, Preview evidence, business-registration evidence, legal/support versions, lead-intake configuration and payment-provider configuration.
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

- BUSINESS_REGISTRATION_READY: PASS
- LICENCE_READY: PASS
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
- FINAL_COMMERCIAL_DOMAIN: PASS / `lundusdigital.com`
- DNS_PRODUCTION_BINDING: HOLD
- EMAIL_PROVIDER_SELECTED: PASS / Zoho Mail Lite 10 GB
- EMAIL_DNS_AUTHENTICATION: PASS
- OFFICIAL_COMMERCIAL_EMAIL: PASS
- SUPPORT_COMPLAINT_CHANNEL: PASS_INBOUND
- ACTIVATION_SNAPSHOT: HOLD_NOT_FORMED
- PUBLIC_PAYMENT_ACTIVATION: HOLD
- PUBLIC_LAUNCH: HOLD

## 13. Stop conditions

Do not activate public payment if any of these are true:
- business-registration evidence is expired, superseded or cannot be revalidated
- required legal/business particulars for public use remain placeholder or unverified
- domain/DNS/email Production configuration fingerprint is missing or stale
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
- DNS record mutation
- email Production activation
- secret/configuration changes
- public launch
- widening of payment, fulfilment, notification or deployment authority

Those remain separately human-gated.
