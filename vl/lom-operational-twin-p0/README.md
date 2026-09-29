# LOM Operational Twin P0

Status: DEVELOPMENT / NON-PRODUCTION / READ-ONLY COMPOSITION

## Objective

Provide one evidence-bound operational snapshot across LOM without creating a second source of truth.

The Operational Twin composes canonical outputs from:
- LOM 6.10 Project State Truth;
- LOM 6.11 Live Operational Evidence Fabric;
- LOM Organism Integration / homeostasis;
- LOM authority and policy decisions;
- optional bounded next-action recommendations.

It does not replace any authoritative registry, ledger, policy engine, executor, project-state runtime or evidence store.

## Core loop

`OBSERVE -> VERIFY -> UNDERSTAND -> POLICY_GATE -> DECIDE -> ACT_BOUNDED -> VERIFY_RESULT -> RECORD -> LEARN`

P0 implements the read-only `OBSERVE -> VERIFY -> UNDERSTAND -> POLICY_GATE -> DECIDE` composition surface.

## Snapshot contract

For every project, the twin exposes:
- evidence-bound project state;
- evidence freshness;
- body/homeostasis state;
- authority class;
- blocker/reason;
- next action;
- whether autonomous preparation is permitted;
- whether human review is mandatory.

## Fail-closed invariants

- missing or malformed Project State Truth => HOLD;
- missing/stale material evidence => HOLD;
- homeostasis HOLD/FAILED => HOLD;
- unknown authority => HUMAN_REVIEW/HOLD;
- Production, protected-main merge, financial, legal, pricing, bid and customer commitments => HUMAN_ONLY;
- autonomous ceiling remains PREPARE_PR;
- no connector, shell, deployment, database mutation or external write occurs here;
- no positive state may be synthesized from absence of evidence.

## Relationship to existing capabilities

This layer is a projection/coordination surface only.

It consumes existing canonical components rather than duplicating:
- portfolio registry;
- Project State Truth;
- Evidence Fabric;
- Decision Twin;
- Operational Safety;
- organism/homeostasis;
- Director Exception Queue;
- VPS executor.

## P0 acceptance

P0 is acceptable only if deterministic tests demonstrate:
1. verified healthy evidence produces an observational READY snapshot;
2. stale/missing evidence fails closed;
3. HOLD/FAILED body state blocks progression;
4. HUMAN_ONLY actions never become autonomous;
5. LOW-risk reversible non-Production work can reach PREPARE_PR only;
6. output includes a deterministic snapshot digest.

No Production authority is introduced.
