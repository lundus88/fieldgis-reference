# LOM 4.3 Self-Improvement Runtime

Status: DEVELOPMENT / NON-PRODUCTION

LOM 4.3 turns the existing learning and safety layers into a bounded self-improvement runtime:

Observe → Diagnose → Design Improvement → Sandbox → Self-Test → Compare → Prepare PR → Human Approval → Learn

The runtime may autonomously analyze evidence, propose changes, stage low-risk reversible non-production improvements, run deterministic tests, compare before/after scores, and prepare a pull request. It may not self-approve or cross HUMAN_ONLY boundaries.

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
