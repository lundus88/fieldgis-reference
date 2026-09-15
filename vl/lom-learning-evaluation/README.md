# LOM 4.2 Learning & Evaluation Layer

Status: DEVELOPMENT / NON-PRODUCTION

LOM 4.2 adds governed organizational learning on top of LOM 4.1 Operational Safety Hardening. It converts validated decisions, human corrections, outcomes, and golden scenarios into measurable evaluation evidence without permitting self-expansion of authority.

Learning may improve recommendations, routing, prompts, evaluations, and proposed policies; it may not widen authority. Human corrections are immutable evidence records. Policy changes are PROPOSE_ONLY until explicit human approval. Production, commercial, legal, financial, and protected-main boundaries remain HUMAN_ONLY.

## Trust & Confidence Calibration

The Trust & Confidence Engine extends existing confidence and outcome scoring rather than replacing them. Raw confidence is treated as an uncalibrated claim until it is compared with historical outcomes.

Calibration uses:
- historical asserted-confidence versus observed correctness;
- Brier score and expected calibration error;
- evidence quality and freshness;
- empirical source and model reliability;
- independent validation;
- safety status;
- agent/model disagreement.

Fail-closed rules:
- stale evidence, missing independent validation, invalid authority, failed safety, very low evidence quality, severe disagreement, or very low empirical reliability => `HOLD`;
- insufficient calibration history or material miscalibration => `REVIEW`;
- `TRUSTED` means calibrated decision support only. It grants no execution authority.

Authority invariants:
- `production_locked = true`;
- `execution_authority = NONE`;
- `authority_effect = NONE`;
- autonomous ceiling remains `PREPARE_PR`;
- protected-main merge and Production remain HUMAN_ONLY.

Release Candidate requires deterministic regression tests and exact-head repository CI before any merge to protected main.
