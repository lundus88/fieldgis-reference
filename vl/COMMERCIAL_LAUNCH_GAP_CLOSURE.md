# VL Commercial Launch Gap Closure

Status: in progress
Scope: close the remaining gap between Controlled Public Beta and full commercial public readiness without weakening production governance.

## Gate A — Public onboarding
- [x] Controlled pilot account signup/sign-in exists.
- [x] Terms acceptance and account state are recorded.
- [x] Support request path exists.
- [x] Voice/text input can create draft App Specs only.
- [x] Assisted Build / Business Interview flow produces a structured, user-confirmed draft App Spec with provenance and assumptions. Evidence: `VL Assisted Build Contract #22` PASS on PR #106 head `04992fc3e325b1a25bd8739a6cd4918d75a2e4c8`.
- [x] Customer-facing build status and failure/retry explanation are verified end-to-end. Evidence: PR #111 added an authenticated RLS-backed read-only `build-status.html` with explicit state/failure/retry explanations and no factory-state mutation path; `VL Launch Recovery Contract #1` PASS. PR #112 linked the status view from the Pilot Portal; Governance #272, Launch Recovery Contract #2, Assisted Build Contract #24 and Voice Runtime #33 all PASS.

## Gate B — Active builder isolation
- [x] web-react-v1 generated build runs in generated-code sandbox.
- [x] pwa-react-v1 generated build runs in generated-code sandbox.
- [x] gis-web-v1 generated build runs in generated-code sandbox.
- [x] api-service-v1 generated validation runs in generated-code sandbox.
- [x] mobile-flutter-v1 generated analyze/build path runs in a credential-free sandbox with bounded resources and no network by default. Evidence: `VL Mobile Sandbox Regression #27` PASS on PR #106 head `04992fc3e325b1a25bd8739a6cd4918d75a2e4c8`.
- [x] Mobile adversarial regression proves OIDC, service-role, network and workspace isolation, including canonical reserved-path traversal cases. Evidence: `VL Mobile Sandbox Regression #27` PASS.

Experimental builders (`ai-app-v1`, `desktop-tauri-v1`) are explicitly outside the commercial active-builder guarantee until separately certified and activated.

## Gate C — Payments
- [x] Billplz sandbox order creation evidence exists.
- [x] Signed paid webhook verification exists.
- [x] Fulfillment evidence exists.
- [x] Reconciliation PASS evidence exists.
- [x] Production payment tables remain isolated from sandbox tests.
- [ ] First live production payment certification is completed by an explicitly authorized human using the bounded live-test path.
- [x] Refund/cancel/duplicate webhook recovery behavior is verified before unrestricted public billing. Evidence: governed payment recovery migration from PR #111 is live. Transactional rollback drill proved `pending -> cancelled`, duplicate cancellation returns `duplicate=true` with no mutation, late `paid` after cancellation returns `terminal_order_not_resurrected`, and `pending -> paid -> fulfilled -> refunded` ends with `fulfillment_state=reversed`. Post-rollback verification showed zero canary order, webhook, or fulfillment rows. No production payment was performed.

## Gate D — Scale and resilience
- [x] Concurrency test demonstrates bounded queue/lease behavior under representative burst load. Evidence: `VL Gate D Resilience #1` PASS on PR #108: 24 queued jobs + 48 simultaneous claimers produced 24 unique leases, 24 idle results, zero duplicate job IDs, and exactly 24 total attempts. Production schema was inspected read-only and confirms `claim_vrs_runner_job` uses `FOR UPDATE SKIP LOCKED`.
- [x] Retry/idempotency test proves duplicate submissions do not create duplicate externally effective actions. Evidence: `VL Gate D Resilience #1` PASS: 32 simultaneous attempts for one action key produced exactly 1 recorded action and 31 duplicates; runner completion replay with the same lease was rejected. Production read-only schema confirms unique runner factory-run, payment event-key, and notification idempotency constraints.
- [x] Provider outage drill proves fail-closed behavior for unavailable payment/deployment/notification adapters. Evidence: production billing resolver returns `blocking=true` / `resolution=missing` without a certified/candidate payment adapter; rollback-only deployment simulation made `supabase-edge-function` unavailable and `claim_vrs_production_promotion_job` returned `idle` while the canary stayed queued with attempts=0; rollback-only Resend simulation made notification readiness return `production_send_allowed=false`. Both transactional simulations were rolled back and live adapter state was verified restored.
- [x] Recovery drill proves stuck/expired leases can be reconciled without bypassing lifecycle gates. Evidence: `VL Gate D Resilience #1` PASS: expired lease reclaimed with a new token, old token rejected, attempt incremented to 2, and successful completion stopped at `validating` rather than approval/production. Production read-only function inspection confirms expired-lease recovery and invalid/expired lease rejection.
- [x] Cost/rate-limit controls are verified for customer and founder/internal modes. Evidence: governed founder/internal guardrail migration from PR #108 is live; policy enforces daily, concurrent, and estimated-cost limits, AAL2 owner/admin time-bounded overrides, classification, ledger and audit. Rollback-only runtime canary proved a staging + production-locked owner run records cost/classification/audit and post-rollback verification showed zero persisted factory-run, runner-job, ledger, audit, or override canary rows. Issue #70 completed.

Gate D machine-readable evidence artifact: `vl-gate-d-resilience-evidence`, artifact id `9782061051`, SHA-256 `ee59a7aefd0519d8e1affeede9292d913e480cba1c2ebf56e01b892dc6209c57`, retained 90 days from `VL Gate D Resilience #1`. Issue #107 completed after production-equivalent rollback simulations closed the provider-outage and founder/internal implementation gaps.

## Gate E — Production governance
- [x] Explicit human production approval remains mandatory.
- [x] Autonomous agents cannot approve production.
- [x] ACP scope/capability escape fails closed.
- [x] Immutable artifact/provenance reconciliation exists.
- [x] Production promotion, verification and rollback workflows exist.
- [ ] Final commercial launch review confirms no open P0 launch blocker.

## Decision rule
Full commercial public launch is GO only when all unchecked items above are supported by fresh machine-readable or independently inspectable evidence. No checklist item may be marked complete solely because a workflow is green; the evidence must prove the intended control.
