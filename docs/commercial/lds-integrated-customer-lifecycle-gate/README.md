# LD Unified Commercial Control Plane v1

Status: DEVELOPMENT / NON-PRODUCTION

This evolves the existing Integrated Customer Lifecycle Gate into the canonical orchestration layer for LD commercial state transitions. It composes evidence from existing modules; it does not replace their source records.

## Principle

**Any qualified customer. Any supported market. One digital workflow.**

North Star:

**From any legitimate lead in the world to a completed paid digital service with minimal human friction.**

## Canonical state graph

VISITOR
→ ASSESSMENT
→ QUALIFIED
→ BLUEPRINT_APPROVED
→ QUOTATION_APPROVED
→ CONTRACT_ACCEPTED
→ PAYMENT_RECONCILED
→ KICKOFF_APPROVED
→ BUILDING
→ QA_PASSED
→ CUSTOMER_ACCEPTED
→ DELIVERED
→ SUPPORT_ACTIVE / RENEWAL_REVIEW / CLOSED

The detailed allowed transitions and dependency/evidence requirements are versioned in `state_graph.json`.

## Control-plane responsibilities

For each requested transition the control plane must verify:

1. the transition is legal from the current state;
2. required dependency modules are ready;
3. required evidence references are present and current;
4. required human authority is represented by an explicit approval receipt;
5. the idempotency key has not already been consumed;
6. no stale/contradictory evidence flag is present.

A PASS authorizes only the logical lifecycle transition for the calling system. It does not mutate an external source of truth by itself.

## Transition receipt

Every consequential PASS produces a deterministic transition receipt containing:

- customer / organization identifier;
- from-state and to-state;
- actor identifier;
- approval timestamp;
- evidence references;
- dependency snapshot;
- idempotency key;
- receipt digest.

The receipt is evidence of the decision. It is not payment evidence, a digital signature, or Production deployment authority.

## Dependency posture

The control plane can reference current and planned LD capabilities, including:

- Workflow Assessment
- Global Commerce Readiness
- Global Transaction Compliance
- Pricing / Estimation Intelligence
- Commercial Document System
- Contract & Digital Acceptance
- Fraud / Payment Abuse Protection
- Payment Reconciliation
- Customer Organization / IAM
- Subscription & Entitlement
- SLA / Reliability
- Data Governance & Retention
- Usage / Cost Metering
- Observability / Cost Anomaly

A module's readiness never substitutes for transition evidence or human authority.

## Hard safety rules

- advisory modules cannot advance hard state;
- payment redirect is never reconciliation evidence;
- material scope change requires an approved Change Request before changed-scope build continues;
- duplicate/replayed transition requests are idempotent and must not create a second transition;
- cross-organization authority is invalid;
- missing, stale or contradictory hard-gate evidence returns HOLD;
- Production deployment, live charging, destructive data action and privilege elevation remain separate HUMAN_ONLY authorities.
