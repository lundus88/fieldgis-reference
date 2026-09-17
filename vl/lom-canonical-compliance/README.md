# LOM Canonical Maturity & Compliance Chain

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #248

Purpose: reconcile the existing LOM 4.3 through 6.10 stack into one machine-testable canonical chain without reimplementing capabilities that already exist.

This package is a compliance/reconciliation layer, not a second self-improvement, sandbox, promotion, approval, evidence-ledger or project-state runtime.

## Canonical authority

- autonomous ceiling: `PREPARE_PR`
- Production authority: `HUMAN_ONLY`
- protected-main merge: `HUMAN_ONLY`
- self-approval: `FORBIDDEN`
- missing evidence: `HOLD`
- unknown authority: `HOLD`

## What the validator proves

The validator requires unique stage IDs, unique canonical owners and unique canonical artifact ownership; verifies that every declared canonical artifact exists; verifies selected hard authority/evidence tokens in critical runtime files; and prevents an open/pending stage from being declared canonical before it is merged.

## Canonical promotion rule

A stage may move from `pending_external_stages` to `canonical_stages` only after its governed pull request has been human-approved, required CI has passed, and the stage has been merged into protected `main`. LOM 6.10 satisfies this condition through merged PR #260 and is therefore eligible for canonical registration.

Future unmerged stages must remain pending and must not be recreated inside this package.

## Release boundary

This package may report PASS for repository structure and invariants only. It does not authorize merge, deployment, Production mutation, Production approval, authority widening, external consequential actions, or financial/commercial commitments.
