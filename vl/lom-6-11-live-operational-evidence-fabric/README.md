# LOM 6.11 — Live Operational Evidence Fabric

Status: **DEVELOPMENT / NON-PRODUCTION**

LOM 6.11 standardizes live operational evidence across the registered portfolio without creating a second telemetry engine, project registry, evidence ledger, state engine, or scheduler.

## Purpose

6.11 composes existing LOM capabilities:

- `vl/lom-portfolio-runtime/source-registry.json` remains the single portfolio source catalog.
- LOM 6.3 remains the technical telemetry normalizer.
- LOM 6.3.1 remains the live read-only evidence adapter.
- LOM 6.3.2 remains the technical metrics artifact contract.
- LOM 6.3.3 remains the metric semantics registry.
- LOM 6.10 remains the canonical Project State Truth engine.
- Mission Control remains the Director control surface.

6.11 adds the missing portfolio-wide evidence fabric between those layers.

## Standard operational signals

Accepted evidence types:

- `CI_RUN`
- `RUNTIME_HEALTH`
- `AUTH_PATH`
- `DEPLOYMENT_STATE`
- `BACKGROUND_JOB`

Minimum evidence required for an operational readiness candidate:

- `CI_RUN`
- `RUNTIME_HEALTH`

Authentication, deployment and background-job evidence remain explicit coverage dimensions. Missing recommended signals are reported; they are never fabricated.

## Fail-closed rules

Evidence is held when any of the following applies:

- unknown or unregistered project evidence;
- scope/repository mismatch;
- invalid or missing Git SHA;
- missing provenance/source reference;
- stale or future timestamps;
- production-sensitive evidence;
- invalid latency or error-rate values;
- malformed deployment/job state;
- contradictory signal evidence;
- required operational signal missing;
- required signals refer to different SHAs;
- technical metrics fail the existing LOM 6.3 normalizer.

A project is only emitted as a `VERIFIED` **truth candidate** when the minimum operational evidence is complete, successful, SHA-consistent, fresh, and contains independent validation. 6.11 does not itself approve or release a project. Canonical state authority remains with LOM 6.10.

## Metric semantics alignment

The 6.3.3 semantics registry is extended to every current `READ_ONLY` project in the portfolio source registry:

- VL / VRS Labs
- e-BKL
- SabahLot
- LundusLead
- UrusMY
- KontenStudio

SLP remains excluded while its authoritative source is `UNREGISTERED_HOLD`.

## Authority invariants

- autonomous ceiling: `PREPARE_PR`
- protected-main merge: `HUMAN_ONLY`
- Production authority: `HUMAN_ONLY`
- execution authority: `NONE`
- execution performed: `False`
- cross-repository write: `DISABLED`
- production-sensitive evidence: `FORBIDDEN`
- fabricated metrics/evidence: `FORBIDDEN`
- missing or stale evidence: `HOLD`

This stage is read-only and observational. It introduces no Production deploy, data mutation, financial action, protected-main merge authority, or self-approval capability.
