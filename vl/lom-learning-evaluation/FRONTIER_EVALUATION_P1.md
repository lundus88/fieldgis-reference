# LOM 4.2 P1 — Frontier Evaluation & Adversarial Audit Scorecard

This extends the existing Learning & Evaluation Layer. It does not create a second evaluator, red-team engine, learning engine or governance authority.

## Purpose

LOM may aspire to frontier capability, but it must prove capability with evidence rather than self-description.

The scorecard measures eight system dimensions:

1. REASONING
2. TOOL_USE
3. LONG_HORIZON
4. MEMORY
5. ROBUSTNESS
6. EVIDENCE
7. EFFICIENCY
8. GOVERNANCE

Existing Red-Team Chaos evidence is consumed as the adversarial robustness input. The scorecard does not duplicate those attack scenarios.

## Evidence rules

Every benchmark observation requires:

- addressable evidence;
- fresh evidence;
- independent validation;
- evaluator identity different from executor identity;
- bounded score in [0,1].

External comparison requires a named reference system and comparable reference score.

## Claim discipline

Internal evidence can establish `INTERNAL_FRONTIER_READY`.

Comparable external evidence across all dimensions can establish `FRONTIER_CANDIDATE` when all comparisons favor LOM.

Neither status means world-best.

LOM is explicitly forbidden from self-certifying a global superiority claim:

`world_best_claim = FORBIDDEN`

A global claim would require independent external benchmark coverage and third-party review outside this runtime.

## Improvement loop

Missing or below-threshold dimensions may emit `PROPOSE_ONLY` evaluation improvement candidates. They have no authority effect and may only enter the existing bounded closed-loop through the normal Self-Improvement / Decision Twin / CAIE gates.

## Human sovereignty

- execution authority: NONE
- autonomous ceiling: PREPARE_PR
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-certification: FORBIDDEN
- authority effect: NONE
