# VL Commercial Launch Gap Closure

Status: in progress
Scope: close the remaining gap between Controlled Public Beta and full commercial public readiness without weakening production governance.

## Gate A — Public onboarding
- [x] Controlled pilot account signup/sign-in exists.
- [x] Terms acceptance and account state are recorded.
- [x] Support request path exists.
- [x] Voice/text input can create draft App Specs only.
- [x] Assisted Build / Business Interview flow produces a structured, user-confirmed draft App Spec with provenance and assumptions. Evidence: `VL Assisted Build Contract #22` PASS on PR #106 head `04992fc3e325b1a25bd8739a6cd4918d75a2e4c8`.
- [ ] Customer-facing build status and failure/retry explanation are verified end-to-end.

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
- [ ] Refund/cancel/duplicate webhook recovery behavior is verified before unrestricted public billing.

## Gate D — Scale and resilience
- [x] Concurrency test demonstrates bounded queue/lease behavior under representative burst load. Evidence: `VL Gate D Resilience #1` PASS on PR #108: 24 queued jobs + 48 simultaneous claimers produced 24 unique leases, 24 idle results, zero duplicate job IDs, and exactly 24 total attempts. Production schema was inspected read-only and confirms `claim_vrs_runner_job` uses `FOR UPDATE SKIP LOCKED`.
- [x] Retry/idempotency test proves duplicate submissions do not create duplicate externally effective actions. Evidence: `VL Gate D Resilience #1` PASS: 32 simultaneous attempts for one action key produced exactly 1 recorded action and 31 duplicates; runner completion replay with the same lease was rejected. Production read-only schema confirms unique runner factory-run, payment event-key, and notification idempotency constraints.
- [ ] Provider outage drill proves fail-closed behavior for unavailable payment/deployment/notification adapters. Ephemeral harness PASS exists and production read-only inspection confirms deployment adapter fail-closed/unconfigured behavior plus notification approval/evidence gates, but a production-equivalent payment/notification outage drill is still required before closing this item.
- [x] Recovery drill proves stuck/expired leases can be reconciled without bypassing lifecycle gates. Evidence: `VL Gate D Resilience #1` PASS: expired lease reclaimed with a new token, old token rejected, attempt incremented to 2, and successful completion stopped at `validating` rather than approval/production. Production read-only function inspection confirms expired-lease recovery and invalid/expired lease rejection.
- [ ] Cost/rate-limit controls are verified for customer and founder/internal modes. Ephemeral policy harness PASS proves intended semantics, but production founder/internal implementation remains separately gated by Issue #70 and is not considered closed.

Gate D machine-readable evidence artifact: `vl-gate-d-resilience-evidence`, artifact id `9782061051`, SHA-256 `ee59a7aefd0519d8e1affeede9292d913e480cba1c2ebf56e01b892dc6209c57`, retained 90 days from `VL Gate D Resilience #1`.

## Gate E — Production governance
- [x] Explicit human production approval remains mandatory.
- [x] Autonomous agents cannot approve production.
- [x] ACP scope/capability escape fails closed.
- [x] Immutable artifact/provenance reconciliation exists.
- [x] Production promotion, verification and rollback workflows exist.
- [ ] Final commercial launch review confirms no open P0 launch blocker.

## Decision rule
Full commercial public launch is GO only when all unchecked items above are supported by fresh machine-readable or independently inspectable evidence. No checklist item may be marked complete solely because a workflow is green; the evidence must prove the intended control.
