# LOM Complete Body — Canonical Status Report

Status: NON-PRODUCTION / EVIDENCE-BOUND

## Capability status

| Capability | Status | Authoritative owner | Evidence / blocker |
|---|---|---|---|
| Brain / reasoning / planning | EXISTING | Gate E + Agentic OS | governed orchestration and model/runtime tests |
| Sense / telemetry | EXISTING | lom-system-health-p0 | health/drift + operational evidence |
| Memory / evidence lineage | EXISTING | Project State Truth + event/lineage components | append-only evidence and recovery memory |
| Nervous system | EXISTING | Gate E + ACP | default-deny policy routing |
| SRE / Operations | EXISTING | lom-system-health-p0 | health/drift regression |
| Cyber immune / Security | EXISTING | lom-security-hardening | authority alignment + adversarial checks |
| Software engineering | EXISTING | VL Factory Runner | non-Production governed factory |
| Independent QA / Verification | EXISTING | completion-governance | builder self-report is not trusted |
| Recovery / Incident command | EXISTING | Gate D remediation | bounded reversible remediation |
| Observability | EXISTING | lom-system-health-p0 | telemetry, evidence and drift |
| Data / Knowledge engineering | PARTIAL | lom-knowledge-foundation | registry exists; runtime binding candidate in PR |
| Supply-chain guardian | EXISTING | VL Supply Chain Attestation | provenance + SPDX SBOM gate |
| FinOps / Resource controller | PARTIAL | lom-4-5 resource intelligence | cost/capacity controls; consequential billing remains human |
| Autonomy controller | EXISTING | lom-operational-safety | default deny + HUMAN_ONLY actions |
| Capability registry | EXISTING | lom-governance | one capability -> one owner -> many consumers |
| Self-healing / Homeostasis | PARTIAL | lom-organism-integration-p0 | bounded non-Production recovery only |
| VPS always-on execution | BLOCKED | lom-vps-execution-node-p0 | LIVE_VPS_CANARY_NOT_PROVEN |
| HR | NO_DUPLICATE | HR Adapter + specialist HRMS | no second payroll/attendance/leave engine |
| Specialist domains | ON_DEMAND | capability-specific specialist | no permanent duplicate agents |

## Canonical core values doctrine

LOM governance now binds ten core operating values in `core-values-doctrine.json`:

- Evidence Before Action
- Reversible by Default
- Fail Closed, Recover Gracefully
- Single Source of Truth
- Provenance Everywhere
- Capability Before Autonomy
- Measure Before Scale
- Economic Intelligence
- Independent Verification for High-Risk Outputs
- Institutional Memory, Not Repetition

These are governance constraints, not new duplicate modules. Registry validation must fail if the canonical doctrine, its human-authority protections, vendor-neutral core rule or anti-duplication invariant drifts.

## Controlled loop target

`Sense -> Establish Truth -> Retrieve Authoritative Knowledge -> Reason -> Plan -> Policy Gate -> Execute Bounded Sandbox -> Independent Verify -> Record Evidence -> Recover/Learn -> Result`

## Fail-closed conditions

HOLD or HUMAN_REVIEW is mandatory when:
- authority or jurisdiction is unknown;
- authoritative sources conflict;
- confidence or evidence is insufficient;
- permission is absent or wider than delegated scope;
- body/homeostasis is HOLD or FAILED;
- Production, financial, legal, customer, destructive, secret or authority actions are requested.

## Human-only authority

- protected-main merge;
- Production deploy/release/promotion/rollback;
- Production data mutation or deletion;
- security/credential/permission widening;
- payment, billing and material financial commitments;
- legal/contractual and customer commitments;
- live VPS activation after real canary evidence.

## Remaining blocker

The sole external runtime blocker for the always-on heart is a real non-Production VPS canary. Repository or synthetic CI evidence cannot substitute for it.
