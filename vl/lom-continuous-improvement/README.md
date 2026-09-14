# LOM 4.4 Continuous Improvement Orchestrator

Status: DEVELOPMENT / NON-PRODUCTION

LOM 4.4 composes the validated LOM 4.3 Self-Improvement Runtime into a recurring, evidence-bound orchestration loop.

Observe backlog → Qualify evidence → Prioritize candidates → Stage reversible non-production change → Run validation → Compare outcome → Prepare PR → Human Approval → Learn

## Goals
- continuously surface improvement opportunities from validated evidence
- rank only evidence-ready candidates
- stage only low/medium-risk reversible non-production changes
- require deterministic validation and independent verification before PREPARE_PR
- preserve immutable improvement records
- stop at human approval for protected-main merge and Production

## Hard boundaries
The orchestrator MUST NOT:
- merge protected main
- deploy or release Production
- mutate Production data
- widen authority
- change critical auth/security policy
- delete protected data
- make customer, bid, pricing, contract, legal, or financial commitments
- treat missing/contradictory/stale/unknown evidence as PASS
- self-certify or self-approve

Unknown targets fail closed. High-risk, irreversible, Production, and HUMAN_ONLY targets escalate or hold.

## Orchestration disposition
A candidate may advance only through these bounded states:

DISCOVERED → QUALIFIED → PRIORITIZED → SANDBOX → VALIDATED → PREPARE_PR

Any failed control produces HOLD, REJECT, or ESCALATE. PREPARE_PR is not merge authority.