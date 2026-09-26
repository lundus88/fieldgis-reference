# LOM Operational Twin World Model P2

Status: DEVELOPMENT / NON-PRODUCTION / READ-ONLY PROJECTION

## Objective

Extend the existing LOM Operational Twin into a deterministic World State Graph without creating a second source of truth.

P2 composes existing canonical evidence into a graph that can answer:

- which projects and objectives exist;
- which project depends on which other project;
- which Operational Twin snapshot currently represents each project;
- where dependency attention propagates;
- whether graph integrity is complete and non-contradictory.

## Canonical ownership

P2 does not replace or persist over:

- `vl/lom-portfolio-runtime/source-registry.json` — project catalogue;
- LOM 6.10 Project State Truth — project status truth;
- LOM 6.11 Live Operational Evidence Fabric — live evidence;
- Operational Twin P0 — per-project observe/verify/decide projection;
- Control Plane P1 — director exceptions and executive snapshot;
- Event Ledger / Recovery Memory — immutable history and recovery memory.

The graph is a projection only. Canonical truth always outranks the projection.

## P2 graph

Node types:

- `PROJECT`
- `OBJECTIVE`

Edge types:

- `HAS_OBJECTIVE`
- `DEPENDS_ON`

Dependency edges require an evidence reference. Unknown projects, self-dependencies and dependency cycles fail closed.

## Operational semantics

A valid graph may still require human attention when one or more Operational Twin snapshots are `HOLD` or `REVIEW`.

P2 therefore separates:

- **graph integrity**: `READY` or `HOLD`;
- **operational attention**: derived from evidence-bound Twin snapshots.

It never promotes a project to READY, APPROVED, RELEASED or Production-ready.

## Authority invariants

- autonomous ceiling: `PREPARE_PR`
- execution authority: `NONE`
- Production authority: `HUMAN_ONLY`
- protected-main merge: `HUMAN_ONLY`
- self-approval: `FORBIDDEN`
- database mutation: `DISABLED`
- connector execution: `DISABLED`

## Next phase

After P2 is stable, P3 may add a **causal-memory adapter** that reads existing Event Ledger / Recovery Memory / outcome evidence and attaches evidence-backed causal links to the graph. It must not create a competing memory store.
