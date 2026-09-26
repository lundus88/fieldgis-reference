# LOM Core Systems Consolidation Audit

Status: NON-PRODUCTION / ARCHITECTURE-GOVERNANCE ONLY

## Objective

Prevent duplicate core systems by reconciling the current LOM implementation against the intended core architecture.

## Findings

| Core concern | Current canonical implementation | Status | Decision |
|---|---|---|---|
| Model routing / gateway | vl/model-governance + lom-agentic-os-p1 multimodel fabric | EXISTING | REUSE; do not build a second model gateway |
| Capability registry | vl/lom-governance/capability-registry.json | EXISTING | REUSE |
| Observability | vl/lom-system-health-p0 + operational evidence fabric | EXISTING | REUSE |
| Evidence / provenance | Project State Truth + append-only event ledger + lineage chain | EXISTING | REUSE |
| Authority / identity | ACP + authority matrix + secure task ingress + human approval receipts | PARTIAL_CONSOLIDATED | UNIFY CONTRACTS; do not build a second authority engine |
| Event / job semantics | secure task ingress + exception queue + pursuit queue + runtime event journals | PARTIAL_DISTRIBUTED | STANDARDIZE CONTRACTS; do not build a second broker yet |
| Always-on execution | VPS execution node | BLOCKED_RUNTIME | Requires real non-Production VPS canary; no synthetic substitution |

## Proven gaps

### G1 — Canonical Event Contract
LOM has multiple event/task/queue representations with overlapping but non-identical semantics.
The gap is not a missing queue engine. The gap is a shared envelope and lifecycle vocabulary.

Required canonical fields:
- event_id
- event_type
- source_component
- objective_id
- project_id when applicable
- tenant/scope when applicable
- actor_id / producer_id
- occurred_at
- evidence_refs
- idempotency_key
- risk_class
- target_environment
- authority_requirement
- correlation_id
- parent_event_id when applicable
- payload_digest
- payload

Required lifecycle semantics:
RECEIVED -> VALIDATED -> ROUTED -> CLAIMED -> EXECUTING -> VERIFYING -> COMPLETED
with terminal alternates HOLD / ESCALATED / FAILED / CANCELLED.

### G2 — Authority Plane Map
Authority controls exist across ACP, authority matrix, operational safety, secure ingress and human approval packages.
The gap is a canonical map of who owns which decision and where authority is resolved.

Required rule:
Authentication != authorization != capability != execution authority.

### G3 — Dead-letter / reconciliation standard
Existing components implement HOLD, retry bounds, leases and idempotency, but there is no one canonical cross-component rule for poison/unprocessable work.

Required treatment:
- never infinite retry;
- exhausted retry -> HOLD or DEAD_LETTER equivalent;
- reason/evidence required;
- human review for authority/evidence conflicts;
- deterministic replay only after remediation;
- no bypass of policy gate.

## Anti-duplication decision

Do NOT create:
- a second model gateway;
- a second observability stack;
- a second capability registry;
- a second evidence ledger;
- a second authority engine;
- a general-purpose message broker until scale/runtime evidence proves the existing bounded queue architecture is insufficient.

## Runtime boundary

This audit grants no Production authority, no protected-main merge authority, no credential widening, and no live VPS activation.
