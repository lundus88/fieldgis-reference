# LOM Organism Integration P0

Status: DEVELOPMENT / NON-PRODUCTION / INTEGRATION ONLY

## Objective

Complete LOM as one governed operational organism by wiring existing components into a single closed loop:

`SENSE -> ESTABLISH_TRUTH -> CLASSIFY -> POLICY_GATE -> DECIDE -> PREPARE_OR_EXECUTE_BOUNDED -> VALIDATE -> RECORD_EVIDENCE -> LEARN`

This package does not create a new brain, new executor, new evidence store or new authority system. It is the spinal cord and homeostasis contract between systems that already exist.

## Organ map

- **Brain** — Agentic OS, multimodel fabric, CAIE, Gate E orchestrator.
- **Eyes** — telemetry, operational evidence, dashboard.
- **Ears** — events, exception queues, pursuit signals.
- **Nervous system** — Gate E + authority matrix + ACP policy routing.
- **Memory** — Project State Truth, append-only ledger, lineage, recovery memory.
- **Immune system** — security hardening, adversarial checks, remediation governance, rollback.
- **Heart** — Director Loop, continuous-ops cadence, prioritization.
- **Hands** — ACP non-production transition, governed remediation, factory runner.
- **Voice** — Director Brief and human approval package/receipt.
- **Locomotion / legs** — artifact movement, preview, governed promotion and delivery preparation.
- **Skin / boundary** — connector governance, context minimization and external exposure control.
- **Metabolism** — resource, cost, capacity and bottleneck intelligence.

## Homeostasis

Every required organ must provide fresh evidence. Missing, duplicate, stale, unknown or failed organ state cannot be hidden by other healthy components.

Whole-body status is the worst trusted organ state:

`HEALTHY < DEGRADED < HOLD < FAILED`

A missing organ is HOLD.

## Reflex arc

Signals cannot jump directly from sensors to execution.

Every signal is routed through evidence/truth and authority boundaries. Low-risk, reversible non-Production regressions may reach `AUTO_PREPARE`, which means **prepare a candidate only**. It never means merge or Production execution.

Consequential signals always route to HUMAN_REVIEW.

Security signals default to HOLD/containment review.

## Integrated enhancements

PR #386 (Health/Drift/Fact Truth/Human Gate Intelligence) and PR #387 (VPS Execution Node) are now merged into `main`.

- #386 is bound to the **eyes** organ through the fail-closed portfolio-health probe adapter.
- #387 is bound to the **hands** organ through the canary-gated BodyRuntime executor adapter.
- VPS repository code being merged does **not** activate the VPS node. Live execution remains `HOLD_LIVE_VPS_UNVERIFIED` until fresh, non-synthetic `LIVE_VPS_CANARY` evidence passes.
- Neither enhancement changes the autonomous ceiling (`PREPARE_PR`) or any HUMAN_ONLY Production authority.

## Authority boundary

- autonomous ceiling: `PREPARE_PR`
- execution authority of this integration layer: `NONE`
- protected-main merge: HUMAN_ONLY
- Production deploy/data/authority changes: HUMAN_ONLY
- financial, legal and customer commitments: HUMAN_ONLY

This integration package must never convert an observation into consequential authority.


## Whole-body runtime coordinator

`body_runtime.py` converts the organ map into a fail-closed runtime coordinator while preserving the existing canonical executors and authority systems.

Runtime rules:

- every one of the 12 organs is sampled through an explicit probe adapter;
- missing, stale, failed, mismatched or unproven organ evidence blocks consequential progression;
- DEGRADED state may still be observed, but bounded work requires a fully HEALTHY body;
- signals are deduplicated and routed through the existing truth/policy/reflex path;
- bounded work is delegated only to an injected non-Production executor; this integration layer never executes shell, connectors, Production deployment, database mutation or protected-main merge itself;
- the executor must explicitly return `production_locked=true` plus execution evidence;
- evidence recording is mandatory before bounded execution and again at cycle completion;
- learning is proposal-only and cannot mutate authority;
- Production, financial, legal and customer commitments remain HUMAN_ONLY and are converted into a human decision package rather than execution.

This closes the current P0 integration gap between anatomy and runtime coordination. Health/Drift is now a canonical eyes component; the VPS executor bridge is a canonical hands component but remains dormant until live canary evidence is proven.
