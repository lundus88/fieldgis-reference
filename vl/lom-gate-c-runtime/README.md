# LOM 2.0 Gate C — Multi-Agent Task Runtime & Exception Router

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #197

## Purpose
Gate C executes bounded, reversible multi-agent task chains on top of the Gate B planner/executor/validator contract.

## Runtime sequence
1. Planner emits a bounded task graph.
2. Risk Governor classifies every task before execution.
3. Executor runs only delegated non-production/reversible tasks.
4. Validator independently verifies outputs and evidence.
5. Runtime retries only retry-safe failures within policy.
6. Exception Router escalates human-only, unknown-authority, contradictory-evidence, retry-exhausted, or risk-threshold events.
7. Memory Keeper records evidence-backed outcomes and lessons without changing policy automatically.

## Invariants
- HUMAN_ONLY actions never execute autonomously.
- Unknown authority => HOLD/ESCALATE.
- Missing or contradictory evidence => HOLD/ESCALATE.
- No production deployment, release, data mutation, protected-main merge, customer outreach, bid, pricing/quotation commitment, contract/legal commitment, or financial commitment.
- Executor cannot validate its own consequential result.
- Retry cannot widen authority, scope, or risk class.
- Every material state transition is attributable and evidence-linked.
- Runtime is deterministic for identical task/evidence inputs.

## Gate C outputs
- task-runtime state machine
- retry policy
- exception routing contract
- machine-readable run ledger
- regression and adversarial tests
- CI evidence
