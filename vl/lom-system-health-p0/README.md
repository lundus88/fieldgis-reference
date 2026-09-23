# LOM System Health & Drift P0

Status: DEVELOPMENT / NON-PRODUCTION

This layer composes existing LOM evidence, safety and Agentic OS foundations into one fail-closed operational control surface. It does **not** replace the canonical portfolio registry, Evidence Fabric, Project State Truth, CAIE, or existing event ledgers.

## P0 value

### 1. System Health & Drift Engine
Classifies each registered project as:

- `HEALTHY`
- `DEGRADED`
- `HOLD`
- `ACTION_REQUIRED`

The engine requires fresh evidence, exact-main CI identity, runtime state and declared deployment policy. Unknown or stale state never becomes healthy by assumption.

### 2. Production Drift Watch
Compares:

`repository main -> Preview -> Production -> database fingerprint`

Production policy is explicit:

- `LOCKED`: drift may be expected while Production is intentionally held; it is still surfaced.
- `TRACK_MAIN`: drift is an action-required condition.
- `NOT_APPLICABLE`: no Production parity requirement.

This module never deploys, promotes or rolls back Production.

### 3. Automatic Regression Sentinel
Golden journeys are evaluated against an exact main SHA. Missing, stale, skipped or wrong-SHA critical evidence fails closed. A critical journey failure becomes `ACTION_REQUIRED`.

The sentinel evaluates evidence; it does not create authority to execute Production recovery.

### 4. Cross-System Evidence Ledger
A durable JSONL hash chain records health and regression decisions with evidence references. Every append validates the existing chain and fsyncs the record.

P0 ledger integrity is tamper-evident, not a replacement for external cryptographic notarization or legal signing.

## Canonical integration

Use the existing project catalog:

`vl/lom-portfolio-runtime/source-registry.json`

Do not create a second project registry.

Existing components remain authoritative for their own scopes:

- Live Operational Evidence Fabric
- Project State Truth / Director Mission Control
- Agentic OS Eyes, Hands & Continuity
- CAIE governance
- Operational Safety event ledger

This package supplies deterministic health/drift and regression classifications that can be bound into those systems.

## Authority boundary

Autonomous ceiling: `PREPARE_PR`.

Always HUMAN_ONLY:

- protected-main merge
- Production deploy/release/promotion/rollback authority
- Production data mutation
- security or credential widening
- pricing, bid, customer, legal and financial commitments

No Production credentials are added. No database migration is included. No cross-repository write is performed by this P0 module.
