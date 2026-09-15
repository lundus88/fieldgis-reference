# LOM Canonical Maturity & Compliance Chain

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #248

Purpose: reconcile the existing LOM 4.3 through 6.9.3 stack into one machine-testable canonical chain without reimplementing capabilities that already exist.

This package is a compliance/reconciliation layer, not a second self-improvement, sandbox, promotion or approval runtime.

## Canonical authority

- autonomous ceiling: `PREPARE_PR`
- Production authority: `HUMAN_ONLY`
- protected-main merge: `HUMAN_ONLY`
- self-approval: `FORBIDDEN`
- missing evidence: `HOLD`
- unknown authority: `HOLD`

## What the validator proves

The validator requires unique stage IDs, unique canonical owners and unique canonical artifact ownership; verifies that every declared canonical artifact exists; verifies selected hard authority/evidence tokens in critical runtime files; and prevents an open/pending stage from being declared canonical before it is merged.

## Pending work is not duplicated

LOM 6.3.6 critical-safety propagation is tracked independently in PR #246. Until that PR is explicitly human-approved and merged, this package records it as `pending_external_stages` and does not recreate its functionality or count it as merged evidence.

## Release boundary

This package may report PASS for repository structure and invariants only. It does not authorize merge, deployment, Production mutation, Production approval, authority widening, external consequential actions, or financial/commercial commitments.
