# LOM 4.5 — Interoperability & Resource Intelligence

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: add provider-neutral model interoperability and bounded resource optimization without widening production authority.

## Capabilities
- provider-neutral adapter contract and capability discovery
- deterministic provider/model failover
- cost/latency/quality-aware routing score
- global token/cost/step/time budget enforcement
- bounded workload queue with priority and fairness controls
- capacity planning for certified non-production execution pools
- adaptive recommendations only; no autonomous production scaling

## Invariants
- Production release/deploy/data mutation remain HUMAN_ONLY.
- Protected-main merge remains HUMAN_ONLY.
- AUTH_SECURITY_POLICY_CHANGE, AUTHORITY_WIDENING and DATA_DELETION remain HUMAN_ONLY.
- Unknown provider, capability, evidence or resource state fails closed.
- No ambient production credentials.
- Provider failover may only select registered active adapters compatible with privacy and capability policy.
- Optimizer output is advisory or PREPARE_PR at most; it cannot allocate production capacity.
- Budget expansion is forbidden without human approval.

## Autonomous ceiling
`PREPARE_PR`


## Resource continuity

The runtime should preserve capacity before token/quota exhaustion rather than react only after failure.

Default planning thresholds:
- <70% used: NORMAL
- 70-84%: SHED_NON_CRITICAL
- 85-94%: CONTROLLED_MODE
- >=95%: CRITICAL_ONLY

Priority shedding order protects P0/P1 customer support and recovery work before P2/P3 and internal experiments.

### Checkpoint and resume
Long work should create evidence-backed checkpoints containing:
- current step;
- artifact references;
- decision references;
- next action.

A resource-exhausted run should resume from the latest valid checkpoint. Restart-from-zero is not an accepted recovery strategy when checkpoint evidence exists.

### Exhaustion handling
RESOURCE_CONSTRAINED may route to:
- a certified compatible fallback adapter;
- WAITING_CAPACITY when no safe fallback exists;
- HOLD when no valid checkpoint exists.

The runtime must not widen budgets automatically. Additional spend/capacity remains human-controlled.


## OpenAI Responses adapter — P0-02

The provider-neutral layer now includes a governed OpenAI Responses request/response adapter contract in `openai_responses_adapter.py`.

This is an adapter extension, not a second reasoning engine.

P0-02 rules:
- use the Responses API contract;
- use strict structured outputs for machine-consumable results;
- `store=false`;
- tools disabled in this first adapter;
- only YouTube research/script/QA capabilities are in scope;
- only `public` and `internal` data classes are allowed;
- route evidence must be verified and originate from canonical `vl/model-governance`;
- model/provider choice is not made by this adapter;
- no API key, bearer token or credential may appear in the worker/job envelope;
- authentication is injected only by a server-side broker;
- generic worker secret access remains forbidden;
- a live non-production paid call requires independent human approval bound to the exact request digest;
- Production remains locked.

The adapter intentionally accepts route retention evidence of `none` or `30_days` for P0 public/internal content. It does not claim Zero Data Retention unless separately evidenced. Sensitive data classes remain out of scope.

### Activation boundary

Repository merge does not activate a live OpenAI call. Live non-production activation additionally requires:
1. a certified OpenAI model route in canonical model governance;
2. a server-side `lom-openai-nonprod` broker with secret injection;
3. independently verified human approval bound to the request digest;
4. runtime evidence for request, response, usage and cost;
5. no secret leakage.

Until those conditions are proven, P0-02 is CONTRACT/CI evidence only.
