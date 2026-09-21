# Golden Workflow Evidence Capture v2

Status: DEVELOPMENT / NON-PRODUCTION
Authority: Issue #158

Purpose: make every future LOM Golden Workflow produce the mandatory evidence required for Operational Maturity without reconstructing missing facts after the run.

## Capture lifecycle

1. BEGIN — bind request identity, deterministic App Spec/context/model-routing digests, capability/resource scope, budgets and exact source commit.
2. EXECUTE — remain inside the declared authority envelope.
3. VALIDATE — collect QA/security evidence and independent validation.
4. HUMAN GATE — bind the explicit human decision when required.
5. FINALIZE — record outcome, attempts, elapsed time, estimated model/tool cost, remediation, rollback/audit linkage and delegation evidence.
6. PROMOTION CHECK — call the existing Operational Maturity validator. Only complete, safe evidence may be VERIFIED.

## Fail-closed semantics

The capture layer does not invent missing historical evidence. Missing validation, missing human decision, missing artifact evidence, budget overrun, authority expansion, fabricated PASS, autonomous Production approval or builder self-certification prevents promotion and returns PARTIAL.

Historical Golden #1–#4 remain PARTIAL until their missing facts can be recovered from authoritative evidence. They must not be backfilled from assumptions.

## Authority

- autonomous ceiling: PREPARE_PR
- Production approval: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-certification: FORBIDDEN
- evidence promotion: deterministic validation only

This module captures evidence; it does not deploy Production, spend funds, contact customers, submit bids, commit pricing, or widen authority.
