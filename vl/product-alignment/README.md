# VL Product Alignment Gate

This gate prevents VL from treating a technically successful build as a successful product when the founder intent, user outcome, and acceptance evidence are incomplete or contradictory.

## Required flow

Founder Intent → User Requirements → Acceptance Tests → App Spec → Build → QA/Certification → Human Production Approval.

## Founder workflow

Before a new product is allowed to enter enforced build mode, define:

1. Primary user.
2. Core problem.
3. Desired outcome.
4. Must-have capabilities.
5. Must-not behaviours.
6. Success metric.
7. Commercial model.
8. Compliance constraints.
9. Release scope.
10. Human decision boundaries.

Every P0 user requirement must be traceable to Founder Intent and to at least one observable acceptance test. Unresolved contradictions fail closed. Human production approval remains mandatory.

## Validation

Run:

```bash
python3 vl/product-alignment/run_regression_tests.py
```

A valid product-alignment document returns PASS. Missing Founder Intent, unmapped P0 requirements, false traceability, or unresolved contradictions return FAIL.

## Rollout safety

This directory establishes the contract and Governance CI regression suite. Live factory-runner enforcement should be activated atomically with the upstream App Spec/claim producer so legacy jobs are not accidentally blocked before they carry the new alignment payload.
