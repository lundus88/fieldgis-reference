# LOM P0-A — Macro-Evaluation & Trace Learning

Status: DEVELOPMENT / NON-PRODUCTION / READ-ONLY ANALYSIS

## Objective

Evaluate populations of measured LOM traces instead of judging only one run at a time.

P0-A composes existing LOM capabilities:

- Learning & Evaluation Layer — canonical learning proposal authority;
- Intelligence Stack P0 — benchmark/model-routing evidence;
- Live Operational Evidence Fabric — operational evidence;
- Level 8 P3 Causal Memory — independently validated causal/recovery lessons.

It does **not** create a new learning engine, memory store, execution router, model router, or source of truth.

## Core loop

Trace population
→ validate measured evidence
→ aggregate task health
→ detect recurrent failure patterns
→ attach independently validated causal support when available
→ emit PROPOSE_ONLY learning candidates
→ existing Learning/Self-Improvement runtime may evaluate candidates later

## P0 trace contract

Every trace must carry measured values and evidence references:

- trace_id
- project_id
- task_class
- component
- model_id + model_version
- tool_id
- outcome
- failure_code when outcome is not PASS
- correctness
- safety
- evidence_correctness
- tool_success
- latency_ms
- cost_usd
- evidence_refs
- independent-validation flag
- production-sensitive flag

P0 rejects production-sensitive traces.

## Macro rules

Task health is aggregated per project + task class.

A recurrent failure pattern is admitted only when:

- the failure signature is explicit;
- minimum occurrence count is met;
- minimum failure-rate threshold is met;
- every contributing trace has evidence references.

Trace sequence alone never creates causality.

If a matching independently validated known-good recovery exists in Causal Memory P3, it may be attached as causal support. Otherwise the pattern remains observational.

## Learning boundary

P0-A outputs learning candidates only:

- disposition: PROPOSE_ONLY
- execution authority: NONE
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-apply: FORBIDDEN
- memory persistence: NONE

Candidates target existing bounded domains such as EVALUATION, ROUTING, TEST_COVERAGE, OBSERVABILITY, or NON_PROD_WORKFLOW.

No candidate can widen authority or activate Production.
