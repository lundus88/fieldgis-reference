# LOM CAIE P0 — Continuous Autonomous Improvement Engine

Status: DEVELOPMENT / NON-PRODUCTION  
Tracking: Issue #370

CAIE extends the existing LOM Continuous Improvement Orchestrator into an evidence-bound autonomous improvement pipeline:

`Observe → Diagnose → Plan → Sandbox → Test → Score → Remediate → Certify → PREPARE_PR`

## P0 capabilities

- event/schedule/manual trigger contract with attributable evidence
- isolated execution requirement before implementation/testing
- bounded cost, elapsed-time, retry and tool-call budgets
- deterministic task-state history
- multi-dimensional scoring for correctness, safety, regression, UX and performance
- before/after quality comparison
- bounded remediation attempts
- independent certifier requirement
- explicit evidence-consistency gate
- autonomous ceiling fixed at `PREPARE_PR`

## Fail-closed authority model

CAIE must HOLD, REJECT or ESCALATE when evidence, authority, risk, reversibility or budget controls are not satisfied.

CAIE does not grant authority to:
- merge protected `main`
- deploy or release Production
- mutate Production data
- widen authority
- change critical auth/security policy
- self-certify builder output
- make customer, bid, pricing, contract, legal or financial commitments
- delete protected data

Protected-main merge and Production remain HUMAN_ONLY.

## State model

`DISCOVERED → QUALIFIED → PLANNED → SANDBOX → TESTED → SCORED → CERTIFIED → PREPARE_PR`

Failed paths terminate in `HOLD`, `REJECT` or `ESCALATE`.

Remediation is bounded and must return through deterministic testing before scoring/certification.

## Evidence model

Every candidate requires:
- objective and evidence reference
- trigger identity/source/evidence
- target/risk/reversibility/Production classification
- builder and independent-certifier identities
- bounded budget
- deterministic test outcome
- evaluation metrics and baseline evidence
- measured usage
- independent validation
- evidence-consistency result
- immutable task-state history

Missing, stale, contradictory or malformed evidence cannot create PASS.

## P0 acceptance

Run:

`python vl/lom-continuous-improvement/test_caie.py`

The dedicated CI workflow must prove the exact PR head. A successful P0 run terminates at `PREPARE_PR`; it never merges or deploys autonomously.
