# LOM 6.12 — Cognitive Integration Layer

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #347

Purpose: compose existing canonical LOM capabilities into one auditable cognitive decision package without creating duplicate sources of truth.

## Inputs composed, not reimplemented
- LOM 6.10 Project State Truth
- LOM 6.11 Live Operational Evidence Fabric
- Decision Twin / counterfactual evaluation
- Trust & Confidence calibration
- Goal-to-Outcome orchestration
- bounded autonomous remediation / recurrent failure memory
- opportunity / revenue intelligence
- governed learning records

## Cognitive loop
OBSERVE → VERIFY → UNDERSTAND → GENERATE OPTIONS → EVALUATE COUNTERFACTUALS → CALIBRATE CONFIDENCE → APPLY GOVERNANCE → RECOMMEND → PREPARE_PR_OR_HUMAN_REVIEW → LEARN

## Fail-closed rules
- missing, stale, contradictory, or unverified material evidence => HOLD
- unknown authority => HOLD
- Production, protected-main merge, financial, legal, pricing/customer commitment, bid submission, and authority widening => HUMAN_ONLY
- autonomous execution ceiling => PREPARE_PR
- no self-approval
- no synthetic ROI, revenue, demand, eligibility, or safety evidence
- no duplicate project-state, evidence-ledger, recovery, or learning runtime

## High-value additions
1. Unified cognitive decision package with explicit options and evidence.
2. Decision memory references and precedent links.
3. Blast-radius and reversibility classification.
4. Counterfactual comparison fields.
5. Confidence and evidence-freshness fields.
6. Next-best-action with authority classification.
7. Learning hook that is RECORD_AND_PROPOSE_ONLY.

This stage is intentionally advisory/governed. It may prepare a PR or decision package; it does not merge protected main, deploy Production, mutate Production data, spend funds, bind customers, or widen its own authority.
