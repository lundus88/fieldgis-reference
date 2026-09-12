# Lundus Operating Model (LOM) v1

Status: DRAFT / NON-PRODUCTION
Tracking: Issue #154

## Purpose
LOM is the canonical operating framework for governed Level 6 AI execution in VL / VRS Labs.

Canonical lifecycle:

`Request → Plan → Execute → Verify → Human Approval → Release → Audit`

LOM does not grant production authority. Production approval remains human-only and fail-closed.

## Core invariants
1. Default deny for unknown authority, context, tools, connectors, models, execution pools and production transitions.
2. Delegation is monotonic-restrictive: authority, scope, budget and expiry may stay equal or narrow, never widen.
3. An implementer/builder cannot be the sole certifier of its own work.
4. Contract/CI evidence and runtime evidence are separate evidence classes.
5. Every material action must produce attributable machine-readable evidence.
6. Cost, token, retry and time budgets are bounded and observable.
7. Worker agents and generated code receive no ambient production credentials.
8. Release evidence must include rollback and audit linkage.
9. Missing evidence produces HOLD/FAIL, never synthetic PASS.
10. Production approval is human-only.

## Separation of duties
- Orchestrator / Planner: decomposes the objective and assigns bounded work.
- Implementer / Builder: performs implementation within granted scope.
- QA Specialist: executes functional/regression checks.
- Security Reviewer: validates security and authority boundaries.
- Independent Certifier: evaluates evidence independently of the builder.
- Release Preparation Agent: assembles a release candidate and evidence package.
- Human Approver: sole authority for production approval.

## Non-expanding execution envelope
Every model, connector, execution pool and sub-agent hop must consume an execution envelope containing at minimum:
- objective / source-of-truth reference;
- acceptance inventory reference;
- context-policy digest and allowed data classes;
- capability/tool/resource scope;
- cost/token/time/retry ceilings;
- required evidence and terminal states;
- provenance / parent-run identifier;
- fallback constraints;
- target environment;
- production lock state.

A downstream hop may narrow this envelope but must not widen it.

## Mandatory run evidence
Each governed run should capture:
- objective/spec digest;
- App Spec / acceptance inventory digest;
- context-policy digest;
- model-routing decision and policy evidence where a model is used;
- agent identity/version/role;
- capability and resource scope;
- token/cost/time/retry budgets;
- source SHA and artifact SHA-256;
- execution-pool/profile/image identity where applicable;
- QA evidence;
- security review evidence;
- independent validator/certifier evidence;
- remediation history;
- approval state;
- release outcome;
- rollback/audit linkage.

## First LOM Golden Workflow

`Natural-language request → App Spec → governed planning/routing → sandbox implementation → QA → security review → independent validation/certification → release candidate → STOP for human approval`

No autonomous production approval or production deployment is permitted.

## Contract → Runtime Gap Matrix

| Phase | Capability | Contract/CI evidence | In main | Runtime-enforced | LOM status |
|---|---|---:|---:|---:|---|
| 1 | Context Governance | PASS in PR #134 / CI 34027969270 | No | No | GAP |
| 2 | Model Governance + Routing | PASS in PR #135 / CI 34030063155 | No | No | GAP |
| 3 | Completion Contract + Independent Validator | PASS in PR #136 / CI 34030297972 | No | No | GAP |
| 4 | PR/CI Remediation Governance | PASS in PR #137 / CI 34030346317 | No | No | GAP |
| 5 | Certified Connector Framework | PASS in PR #138 / CI 34030396953 | No | No | GAP |
| 6 | Certified Execution Pools | PASS in PR #139 / CI 34030453471 | No | No | GAP |
| 7 | Controlled Multi-Agent Governance | PASS in PR #140 / CI 34030547447 | No | No | GAP |

Important: the Phase 1–7 draft stack is historical contract/CI evidence. It must be reconciled against current `main`; it must not be blindly merged or treated as live runtime proof.

## Existing foundation already in main
LOM builds on existing VL controls already present in `main`, including Agent Control Plane contracts, default-deny authority, capability/resource scope, monotonic delegation, human-only production approval, sandbox/factory governance, certification/release controls, visual preview enforcement, audit concepts and fail-closed production boundaries.

## Activation order
1. Reconcile Phase 1 context governance against current main.
2. Reconcile Phase 3 independent completion validation early, because LOM must never allow builder self-certification.
3. Reconcile Phase 2 model governance before any live model/provider runtime is enabled.
4. Reconcile Phase 5 connector and Phase 6 execution-pool controls before external runtime expansion.
5. Reconcile Phase 4 remediation on non-protected development branches only.
6. Reconcile Phase 7 controlled multi-agent orchestration only after Phases 1–6 have current-main evidence.
7. Execute one non-production LOM Golden Workflow and capture machine-readable runtime evidence.

## Runtime claim policy
LOM uses three explicit evidence states:
- CONTRACT_PROVEN: schema/policy/CI/adversarial evidence exists.
- INTEGRATED: reviewed implementation exists on authoritative main or an approved integration baseline.
- RUNTIME_PROVEN: a real non-production or production runtime execution has machine-readable evidence.

A higher state must never be inferred from a lower one.

## Current status
As of the creation of this document, Issue #128 Phase 1–7 is CONTRACT_PROVEN only. The dedicated implementations remain in draft PRs #134–#140 and are not present on current `main`. LOM therefore remains NOT LEVEL-6 RUNTIME PROVEN.
