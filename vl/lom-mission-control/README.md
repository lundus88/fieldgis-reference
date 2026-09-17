# LOM 2.0 Gate F — Director Mission Control

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: provide one director-facing control surface for objective intake, lifecycle visibility, evidence maturity, agent status, Golden Workflow tracking, operational telemetry, budget/SLO observation, incident and approval queues, exception routing and outcome reporting.

## Existing v1 contract
The original Gate F objective snapshot remains backward compatible:
- objective lifecycle state;
- evidence maturity;
- risk state;
- agent state;
- exceptions;
- deterministic director recommendation.

`mission-control.schema.json` remains the v1 snapshot contract.

## Mission Control v2 additive capabilities
Mission Control v2 extends the existing component rather than introducing a second dashboard or control plane. It adds:
- per-project and per-objective operational telemetry;
- Golden Workflow identifiers and evidence-gap counts;
- incident and critical-incident counts;
- pending human approval counts;
- estimated AI/tool cost against explicit cost budgets;
- elapsed time against time budgets;
- retry counts against retry budgets;
- SLO breach visibility;
- portfolio aggregation across projects;
- governed `PAUSE`, `QUARANTINE`, and `STOP` control intent.

The v2 machine-readable contract is `mission-control-view-v2.schema.json`.

## Canonical Project State Truth integration
LOM 6.10 Project State Truth is the canonical source for project status when Director Mission Control is used in evidence-bound mode.

`truth_bound_mission_control.py` composes the existing v2 Mission Control view with the canonical `lom.project-state-truth/1` snapshot. It does not create another dashboard, ledger, state engine, or execution path.

Use `build_truth_bound_mission_control_view(...)` when project status must be evidence-bound. The existing `build_mission_control_view(...)` remains unchanged for backward compatibility.

Truth-bound behavior is fail-closed:
- missing Project State Truth snapshot -> HOLD;
- invalid schema or weakened authority invariant -> HOLD;
- missing snapshot fingerprint -> HOLD;
- duplicate or malformed project truth -> HOLD;
- telemetry project missing from the truth snapshot -> HOLD;
- canonical state `UNVERIFIED`, `HOLD`, or `FAILED` -> effective HOLD;
- canonical state `VERIFIED`, `APPROVED`, or `RELEASED` permits the existing operational telemetry classification to continue;
- telemetry HOLD still overrides a verified project state;
- Production authority and control execution remain unchanged.

Mission Control surfaces the canonical project state, reason, snapshot fingerprint, and source identifier `LOM_6_10_PROJECT_STATE_TRUTH`. It never treats a displayed `RELEASED` state as authority to perform a release.

## Control semantics
Mission Control never directly executes a control action.

- non-production reversible `PAUSE` / `QUARANTINE` -> `PREPARE_CONTROL` only;
- `STOP` -> `HUMAN_REVIEW`;
- any Production control -> `HUMAN_REVIEW`;
- stale/missing/contradictory control evidence -> `HOLD`;
- irreversible control -> `HUMAN_REVIEW`;
- unknown action/environment -> `HOLD`.

Every control decision reports `execution_authority=NONE` and `execution_performed=false`.

## Fail-closed operational rules
- evidence gap -> HOLD;
- stale or missing telemetry provenance -> HOLD;
- cost/time/retry budget overrun -> HOLD;
- contradictory counters -> HOLD;
- critical incident -> HUMAN_REVIEW;
- pending approval -> HUMAN_REVIEW;
- SLO breach -> HUMAN_REVIEW.

## Non-negotiable authority boundary
- autonomous ceiling: `PREPARE_PR`;
- control execution: `DISABLED`;
- protected-main merge: `HUMAN_ONLY`;
- Production deployment/release: `HUMAN_ONLY`;
- Production data mutation: `HUMAN_ONLY`;
- no authority widening;
- no customer outreach, bid, quotation, contract or financial commitment;
- unknown authority => HOLD;
- missing evidence cannot create PASS;
- builder/agent cannot self-certify consequential actions.

Mission Control may observe, classify, prepare bounded non-production intent and recommend director action. It does not acquire consequential authority.
