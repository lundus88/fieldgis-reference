# LOM Agentic OS P0 — Frontier-Adaptive Intelligence Core

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #357

## Purpose
Unify existing LOM governance, planning, routing, checkpoint, evidence and verification primitives into one vendor-neutral agentic intelligence core.

## Runtime sequence
1. Accept a bounded objective.
2. Classify authority/risk before planning.
3. Build a deterministic bounded plan.
4. Discover only eligible registered tools.
5. Select only certified non-production model/tool routes.
6. Execute only reversible delegated work outside this P0 core.
7. Persist checkpoint envelopes after every material transition.
8. Require independent verification before completion.
9. Escalate HUMAN_GATE / HOLD on authority, evidence, integrity or routing uncertainty.

## Invariants
- Default deny for unknown tools, models, capabilities and authority.
- No live provider invocation in P0.
- No production deployment, promotion, mutation or protected-main merge.
- No payment, refund, pricing, contract, bid, legal or customer commitment.
- No privilege, credential or policy widening.
- Executor cannot self-certify consequential completion.
- Checkpoints and completion decisions are digest-bound.
- Frontier capability intake produces candidate decisions only: ADOPT / PILOT / WATCH / REJECT.
- Existing ACP, Gate C, Operational Safety and Project State Truth controls remain authoritative.

## P0 modules
- deterministic dynamic planner
- model/tool eligibility router
- default-deny tool registry
- checkpoint/resume envelope
- independent verifier
- human-gate classifier
- frontier capability intake evaluator

This package is intentionally standard-library only and does not call external model APIs.
