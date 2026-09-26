# LOM Operational Twin → Control Plane P1

Status: DEVELOPMENT / NON-PRODUCTION / READ-ONLY ADAPTER

## Objective

Connect the merged LOM Operational Twin P0 to the existing LOM Control Plane contracts without creating duplicate registries, ledgers, queues or executive dashboards.

This adapter projects Operational Twin decisions into:
- the existing Director Exception Queue contract;
- the existing Executive Snapshot contract.

It does not replace:
- Project State Truth;
- Live Operational Evidence Fabric;
- Portfolio Runtime;
- Director Exception Queue;
- Executive Snapshot;
- Operational Safety;
- authority policy;
- any executor.

## Mapping rules

Operational Twin:
- `HOLD` -> Control Plane exception;
- `HUMAN_REVIEW` -> Control Plane exception;
- `AUTO_PREPARE` -> no director exception, but autonomy counters may record bounded preparation;
- Production or protected-main merge requests remain HUMAN_ONLY.

Exception categories are mapped conservatively:
- evidence/truth/freshness failures -> `EVIDENCE_GAP`;
- consequential/human-only actions -> `HUMAN_APPROVAL` or `PRODUCTION_TRANSITION`;
- unknown/risk/reversibility constraints -> `RISK_THRESHOLD`;
- body/homeostasis blocking -> `UNRESOLVED_BLOCKER`.

## Safety

- no Production execution;
- no protected-main merge;
- no database mutation;
- no external writes;
- no synthetic PASS;
- autonomous ceiling remains `PREPARE_PR`;
- generated objects are projections only and must not outrank their canonical evidence sources.
