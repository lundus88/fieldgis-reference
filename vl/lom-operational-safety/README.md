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

## Permanent human boundaries

LOM 4.1 does not authorize protected-main merge, production deployment/release, production data mutation, authority widening, customer commitment, bid submission, pricing commitment, contracting, or financial commitment.

## Acceptance

Release Candidate requires exact-head CI success for the adversarial regression suite plus repository governance checks. No production activation is part of this work.
