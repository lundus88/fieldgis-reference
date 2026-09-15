# LOM 4.3 Self-Improvement Runtime

Status: DEVELOPMENT / NON-PRODUCTION

LOM 4.3 turns the existing learning and safety layers into a bounded self-improvement runtime:

Observe → Diagnose → Design Improvement → Counterfactual Evaluate → Sandbox → Self-Test → Compare → Prepare PR → Human Approval → Learn

The runtime may autonomously analyze evidence, propose changes, stage low-risk reversible non-production improvements, run deterministic tests, compare before/after scores, and prepare a pull request. It may not self-approve or cross HUMAN_ONLY boundaries.

## Decision Twin / Counterfactual Evaluation

Decision Twin is an additive evaluation layer inside LOM 4.3, not a separate control plane. It evaluates a proposed improvement against evidence-backed historical runs before the candidate is allowed to enter LOM 6.7 Autonomous Validation Sandbox.

Decision Twin compares baseline and candidate outcomes across multiple runs/projects using:
- success rate;
- HOLD rate;
- correctness;
- safety;
- evidence quality;
- cost;
- latency;
- authority-expansion incidents;
- fabricated-PASS incidents;
- autonomous Production incidents.

The evaluator fails closed when evidence is missing, stale, duplicated or invalid; historical sample/project diversity is insufficient; safety, success, HOLD rate, cost or latency regress beyond policy; or any authority/fabricated-PASS/Production incident is observed.

A positive counterfactual result is only `SANDBOX_CANDIDATE`. It is not approval, execution, merge or deployment authority. The next permitted stage is `LOM_6_7_VALIDATION_SANDBOX`.

Decision Twin outputs a deterministic SHA-256 fingerprint over the candidate, policy and sorted replay evidence so an evaluation can be traced and reproduced.

## Hard boundaries

The following remain HUMAN_ONLY:
- PROTECTED_MAIN_MERGE
- PRODUCTION_RELEASE
- PRODUCTION_DATA_MUTATION
- AUTHORITY_WIDENING
- AUTH_SECURITY_POLICY_CHANGE
- CUSTOMER_COMMITMENT
- BID_SUBMISSION
- PRICING_COMMITMENT
- CONTRACT_COMMITMENT
- FINANCIAL_COMMITMENT
- DATA_DELETION

Unknown targets fail closed. Production targets escalate. High-risk or irreversible candidates cannot be self-staged. A candidate must have READY evidence, regression PASS, independent validation, and no correctness or safety regression before the runtime may emit PREPARE_PR.

Decision Twin itself has `execution_authority=NONE`; protected-main merge and Production authority remain `HUMAN_ONLY`; authority widening is `DISABLED`.

## Improvement Ledger

Every accepted comparison is written as immutable evidence describing:
- observation and evidence reference
- target and proposed change
- before/after score
- measured delta
- regression status
- independent validation status
- final disposition

The runtime never performs protected-main merge or production deployment itself.
