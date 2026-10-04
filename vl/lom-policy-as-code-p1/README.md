# LOM P1 — Policy-as-Code / Machine-Verifiable Governance

Status: DEVELOPMENT / NON-PRODUCTION / VERIFIER-ONLY

## Objective

Make LOM's existing authority invariants machine-verifiable with Open Policy Agent (OPA) / Rego without creating a second governance authority.

Canonical authority remains:

- `vl/lom-canonical-compliance/canonical-chain.json`
- `vl/lom-operational-safety/action-registry.json`

This P1 layer compiles those canonical sources into a deterministic derived policy-data projection, verifies that projection has not drifted, and evaluates representative authority decisions using Rego.

## Architecture

Canonical authority sources
→ deterministic compiler
→ derived policy-data projection
→ Rego verifier
→ ALLOW / HOLD / HUMAN_GATE

OPA never grants authority that is absent from the canonical LOM registries.

## Canonical invariants enforced

- autonomous ceiling = `PREPARE_PR`
- Production authority = `HUMAN_ONLY`
- protected-main merge = `HUMAN_ONLY`
- self-approval = `FORBIDDEN`
- missing evidence = `HOLD`
- unknown authority = `HOLD`
- action registry = default DENY
- Production remains locked
- all registered HUMAN_ONLY actions remain human-gated

## Evaluation priority

P1 policy decisions are deterministic and fail closed:

1. missing evidence → HOLD
2. unknown authority → HOLD
3. self-approval attempt → HOLD
4. protected-main merge → HUMAN_GATE
5. Production action → HUMAN_GATE
6. registered HUMAN_ONLY action → HUMAN_GATE
7. HIGH risk → HUMAN_GATE
8. UNKNOWN risk → HOLD
9. unregistered action → HOLD
10. registered bounded non-production action → ALLOW, capped at PREPARE_PR

## OPA integration

CI uses pinned Open Policy Agent tooling to:

- parse/type-check Rego;
- run Rego unit tests;
- validate the canonical policy projection;
- reject policy/data drift.

P1 does not run an OPA network service and does not change runtime authority.

## Authority boundary

- policy role: VERIFIER_ONLY
- autonomous ceiling: PREPARE_PR
- execution authority: NONE
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-approval: FORBIDDEN
- live policy mutation: DISABLED
- OPA server/network runtime: DISABLED
