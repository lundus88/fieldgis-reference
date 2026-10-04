# Macro-Evaluation P1 — Closed-Loop Learning Binding

This is an extension of the existing Macro-Evaluation capability. It does not create a second learning engine, planner, queue, sandbox or execution runtime.

## Gap closed

Before P1:

Macro traces → recurrent pattern → PROPOSE_ONLY learning candidate → **stop**

After P1:

Macro traces
→ recurrent pattern
→ PROPOSE_ONLY learning candidate
→ existing Self-Improvement Runtime gates
→ existing Decision Twin counterfactual evaluation
→ existing durable CAIE P1 queue
→ existing CAIE validation/remediation/certification
→ PREPARE_PR
→ HUMAN protected-main approval

## Key rule

The adapter never turns correlation into permission.

A Macro-Evaluation candidate cannot enter CAIE merely because it exists. It must first pass the canonical Self-Improvement Runtime and then receive a canonical Decision Twin result of `SANDBOX_CANDIDATE`.

Only then may a durable **non-Production queued task** be created.

Queueing is not execution.

## Risk mapping

This binding uses conservative target-based admission:

- EVALUATION / OBSERVABILITY / TEST_COVERAGE / DOCUMENTATION → LOW
- NON_PROD_WORKFLOW / ROUTING / PROMPT / NON_PROD_CODE / UI_NON_PROD → MEDIUM

Actual CAIE attempts must still independently prove that the attempt is non-Production and reversible.

## Authority invariants

- Macro candidate disposition: PROPOSE_ONLY
- decision-twin execution: FORBIDDEN
- queue-before-Decision-Twin: FORBIDDEN
- queueing does not execute a task
- autonomous ceiling: PREPARE_PR
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-apply: FORBIDDEN

This closes the learning handoff while preserving the existing human authority boundary.
