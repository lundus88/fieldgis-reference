# VL Commercial Launch Gap Closure

Status: in progress
Scope: close the remaining gap between Controlled Public Beta and full commercial public readiness without weakening production governance.

## Gate A — Public onboarding
- [x] Controlled pilot account signup/sign-in exists.
- [x] Terms acceptance and account state are recorded.
- [x] Support request path exists.
- [x] Voice/text input can create draft App Specs only.
- [ ] Assisted Build / Business Interview flow produces a structured, user-confirmed draft App Spec with provenance and assumptions.
- [ ] Customer-facing build status and failure/retry explanation are verified end-to-end.

## Gate B — Active builder isolation
- [x] web-react-v1 generated build runs in generated-code sandbox.
- [x] pwa-react-v1 generated build runs in generated-code sandbox.
- [x] gis-web-v1 generated build runs in generated-code sandbox.
- [x] api-service-v1 generated validation runs in generated-code sandbox.
- [ ] mobile-flutter-v1 generated analyze/build path runs in a credential-free sandbox with bounded resources and no network by default.
- [ ] Mobile adversarial regression proves OIDC, service-role, network and workspace isolation.

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
- [ ] Staging concurrency test demonstrates bounded queue behavior under representative burst load.
- [ ] Retry/idempotency test proves duplicate submissions do not create duplicate externally effective actions.
- [ ] Provider outage drill proves fail-closed behavior for unavailable payment/deployment/notification adapters.
- [ ] Recovery drill proves stuck leases/jobs can be reconciled without bypassing lifecycle gates.
- [ ] Cost/rate-limit controls are verified for customer and founder/internal modes.

## Gate E — Production governance
- [x] Explicit human production approval remains mandatory.
- [x] Autonomous agents cannot approve production.
- [x] ACP scope/capability escape fails closed.
- [x] Immutable artifact/provenance reconciliation exists.
- [x] Production promotion, verification and rollback workflows exist.
- [ ] Final commercial launch review confirms no open P0 launch blocker.

## Decision rule
Full commercial public launch is GO only when all unchecked items above are supported by fresh machine-readable or independently inspectable evidence. No checklist item may be marked complete solely because a workflow is green; the evidence must prove the intended control.
