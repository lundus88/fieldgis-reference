# LOM Agentic OS P1 — Hierarchical Planning & Evidence-Triggered Replanning

Status: DEVELOPMENT / NON-PRODUCTION

This is an extension of the existing Agentic OS planner. It does not create a second planner or execution runtime.

## Capability added

The existing Agentic OS can build a bounded four-step plan. P1 adds a deeper planning contract for long-horizon work:

- hierarchical objective → subgoal decomposition;
- explicit parent/child structure;
- dependency DAG;
- measurable success criteria per node;
- evidence requirements per node;
- deterministic execution waves;
- maximum node/depth budgets;
- uncertainty gate;
- evidence-triggered replanning;
- immutable completed nodes;
- plan lineage and deterministic plan/replan digests.

## Replanning rule

Replanning is not free-form self-direction.

It is allowed only after a supported trigger:

- DEPENDENCY_FAILED
- VALIDATION_FAILED
- TOOL_UNAVAILABLE
- EVIDENCE_CHANGED
- ASSUMPTION_INVALIDATED

The trigger requires fresh evidence.

P1 can change evidence, success criteria and dependency ordering for unfinished work, but it cannot:

- mutate completed nodes;
- change action/capability scope;
- increase risk;
- move work into Production;
- widen authority.

Any requested authority/scope/risk/environment widening goes to HUMAN_GATE.

## Bounded complexity

- maximum nodes: 64
- maximum hierarchy depth: 5
- uncertainty above 0.60: HUMAN_GATE
- HIGH risk: HUMAN_GATE
- Production node: HUMAN_GATE
- non-reversible node: HOLD
- missing evidence/success criteria: HOLD
- cycles/unknown dependencies: HOLD

## Human sovereignty

The planner has no execution authority.

- execution authority: NONE
- autonomous ceiling: PREPARE_PR
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-approval: FORBIDDEN
- authority widening: DISABLED

This capability is intended to improve the measured LONG_HORIZON frontier dimension. It does not self-certify any benchmark improvement; that must be demonstrated separately by the Frontier Evaluation layer.
