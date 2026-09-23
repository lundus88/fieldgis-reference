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

## Candidate enhancements

PR #386 (Health/Drift/Fact Truth/Human Gate Intelligence) and PR #387 (VPS Execution Node) are tracked as enhancements, not dependencies of this P0 body. Their draft state cannot silently become active authority.

## Authority boundary

- autonomous ceiling: `PREPARE_PR`
- execution authority of this integration layer: `NONE`
- protected-main merge: HUMAN_ONLY
- Production deploy/data/authority changes: HUMAN_ONLY
- financial, legal and customer commitments: HUMAN_ONLY

This integration package must never convert an observation into consequential authority.
