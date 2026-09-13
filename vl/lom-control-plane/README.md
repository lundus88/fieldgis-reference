# LOM P2 Operational Control Plane

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #160

## Purpose
LOM P2 turns the merged Lundus Operating Model governance baseline into an operational management control plane for portfolio visibility, evidence-bound state, authority decisions, exception handling, and executive reporting.

## Architecture
The control plane is composed of six contracts:

1. Portfolio Registry — canonical project identity, objective, owner, stage, health, evidence maturity, blockers and next action.
2. State Model — separates portfolio health from evidence maturity and forbids synthetic positive states.
3. Evidence Registry — attributable machine-readable evidence for material decisions and status transitions.
4. Authority Matrix — explicit action classes and approval requirements.
5. Director Exception Queue — management-by-exception interface for decisions that require human attention.
6. Executive Snapshot — compact portfolio, revenue, autonomy and director-attention summary.

## Core invariants
- Unknown authority defaults to deny/hold.
- Missing required evidence produces HOLD or BLOCKED, never PASS.
- `HEALTHY` is not equivalent to `RUNTIME_PROVEN`.
- `RELEASE_CANDIDATE` requires evidence references and remains pre-approval.
- Builder/implementer cannot be sole certifier.
- Production release authority remains human-only.
- Delegated scope may stay equal or narrow, never widen.
- Every material transition records actor, timestamp, provenance and evidence references.

## Canonical portfolio states
- `HEALTHY`
- `REVIEW`
- `BLOCKED`
- `HOLD`
- `RELEASE_CANDIDATE`

## Evidence maturity
- `CONTRACT_PROVEN`
- `INTEGRATED`
- `RUNTIME_PROVEN`

Evidence maturity is orthogonal to portfolio health.

## Management by exception
Routine work inside explicit policy may proceed without director intervention. The Director Exception Queue is used only when one or more of the following applies:
- human-only approval is required;
- authority is unknown or insufficient;
- required evidence is missing or contradictory;
- risk threshold is exceeded;
- a blocker cannot be resolved inside delegated scope;
- a production transition is requested.

## Release boundary
This package does not grant production authority. No schema or policy in this directory may be interpreted as autonomous production approval or deployment authority.
