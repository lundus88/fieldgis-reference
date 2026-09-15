# LOM 4.1 Operational Safety Hardening

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #208

LOM 4.1 hardens the LOM 4.0 decision model before any production-grade autonomous execution is considered.

## Controls

- Centralized Action Registry with explicit capability IDs and default deny.
- HUMAN_ONLY actions always escalate.
- Executor, validator, and remediator identities are explicit and separation is enforced.
- Delegation envelopes are NON_PRODUCTION only and may narrow but never widen capability scope, risk ceiling, expiry, or attempt budget.
- Evidence can never pass when missing, contradictory, stale, or timestamp-invalid.
- ReplayGuard binds `run_id + objective_id + idempotency_key` and rejects duplicate execution.
- AppendOnlyEventLedger hash-chains deterministic events with actor, action, evidence refs, state transition, reason, and timestamp.
- Unknown states fail closed.
- Attempt budgets fail closed when exhausted.

## Autonomous Red-Team & Chaos Lab

The Red-Team & Chaos Lab is an evaluation layer over existing controls, not a second security engine. It runs synthetic hostile scenarios in an isolated non-production simulation and records whether the target control fails closed as expected.

Current scenario classes cover:
- hostile prompt/tool-output markers;
- secret-canary exposure;
- poisoned tool-result schemas;
- connector/capability scope escape;
- stale and contradictory evidence;
- replay attacks;
- risk/authority widening;
- provider outage;
- corrupted artifact digests;
- resource-budget exhaustion;
- executor/validator identity collision;
- Production-action attempts; and
- unknown actions against default-deny policy.

A Red-Team suite reports `PASS` only when every registered attack is blocked, held, or escalated with the exact expected reason. A defense gap returns `HOLD`; missing/invalid scenario contracts fail closed.

Isolation invariants:
- `environment = NON_PRODUCTION`
- `network_access = DISABLED`
- `credential_access = NONE`
- `execution_authority = NONE`
- `execution_performed = false`
- `autonomous_ceiling = PREPARE_PR`

The known-marker untrusted-text check is a conservative reference boundary for regression testing; it is not claimed as a universal prompt-injection detector.

## Permanent human boundaries

LOM 4.1 does not authorize protected-main merge, production deployment/release, production data mutation, authority widening, customer commitment, bid submission, pricing commitment, contracting, or financial commitment.

## Acceptance

Release Candidate requires exact-head CI success for the operational-safety and Red-Team/Chaos regression suites plus repository governance checks. No production activation is part of this work.
