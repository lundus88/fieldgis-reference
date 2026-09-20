# LD Autonomous Operations Layer v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: make standard LD customer work advance automatically after valid commercial gates pass, while preserving explicit human authority for material exceptions.

## Operating principle

**Client triggers the business. LD runs the workflow. Human governs exceptions and authority gates.**

Supporting principle:

**Reliable customer outcome first. Automation is the scaling mechanism.**

## Action modes

- `AUTO` — continue automatically.
- `AUTO_NOTIFY` — continue automatically and surface an operational notification.
- `HUMAN_GATE` — stop until an authorised human decision exists.

## Standard autonomous flow

QUALIFIED_LEAD
→ SMART_CLIENT_DISCOVERY
→ REQUIREMENT_CONFIRMED
→ SCOPE_REVIEW
→ QUOTATION_APPROVED
→ CONTRACT_ACCEPTED
→ PAYMENT_RECONCILED
→ AUTO_KICKOFF_ELIGIBILITY
→ PROJECT_CREATED
→ WORK_PACKAGE_GENERATED
→ BUILDING
→ AUTOMATED_QA
→ SELF_REPAIR_IF_ELIGIBLE
→ PREVIEW_READY
→ CUSTOMER_UAT
→ ACCEPTANCE
→ DELIVERY
→ SUPPORT / RENEWAL

Production deployment is not part of autonomous authority.

## Six high-value controls

### 1. Capability & Service Registry
LD must know what it can safely accept, which offer family applies, dependencies, risk class, supported builder path, and required acceptance evidence.

Unknown or unsupported capability returns HUMAN_GATE or DECLINE/HOLD rather than pretending feasibility.

### 2. Autonomous Capacity & Queue Manager
Before work starts, LD evaluates active workload, concurrency ceiling, customer priority, SLA pressure, estimated effort, and dependency availability.

No new order should silently overload the delivery system.

### 3. Outcome & Acceptance Engine
A project is not complete merely because files were generated or code compiled.

Every project needs explicit outcome criteria derived from the confirmed requirement brief and approved scope.

### 4. Operations Control Tower
Every active project must expose:
- current lifecycle state;
- action mode;
- blocker reason if any;
- next trigger;
- evidence freshness;
- retry/recovery state;
- capacity position;
- commercial/economic status.

### 5. Autonomous Recovery & Rollback
Eligible failures follow:
DETECT → DIAGNOSE → BOUNDED_REPAIR → RETEST → CONTINUE.

If retry/cost/risk limits are exceeded:
→ HUMAN_GATE.

Consequential Production rollback/deployment remains outside autonomous authority.

### 6. Unit Economics & Profit Guard
This layer consumes existing Pricing & Estimation Intelligence rather than duplicating it.

Before autonomous kickoff:
- estimated delivery cost evidence must be current;
- target margin policy must be satisfied or explicitly reviewed;
- third-party recurring costs must be understood;
- capacity pressure cannot silently increase customer price.

## No-idle policy

**No idle project without a documented reason.**

Allowed waiting/block reasons include:
- WAITING_CUSTOMER
- WAITING_PAYMENT
- WAITING_DEPENDENCY
- QUEUED_CAPACITY
- HUMAN_APPROVAL_REQUIRED
- QA_BLOCKED
- RECOVERY_IN_PROGRESS
- EXTERNAL_PROVIDER_OUTAGE
- COMPLIANCE_REVIEW
- COMMERCIAL_REVIEW

Every active non-terminal project must have either:
1. an executable next trigger; or
2. one documented blocker reason and an owner/condition for release.

## Auto-kickoff eligibility

A paid standard order may auto-kickoff only when all are true:
- authoritative payment reconciliation exists;
- confirmed requirement/scope evidence exists;
- requested capability is SUPPORTED;
- delivery capacity is AVAILABLE;
- unit economics status is PASS;
- no unresolved fraud/compliance/security/data-risk condition;
- no material unverified integration dependency;
- no human-only action is required.

The output is an `autonomous_kickoff_eligibility` receipt. It is not Production authority.

## Human-only boundaries

Remain HUMAN_GATE:
- Production deployment/promotion;
- destructive Production data action;
- privilege elevation;
- material contract or scope exception;
- refund/dispute outside approved policy;
- unsupported/high-risk compliance decision;
- secrets/credential handling outside approved secure path;
- irreversible customer-impacting action without rollback evidence.

## Relationship to existing LD modules

This layer composes rather than replaces:
- Smart Client Discovery;
- Unified Commercial Control Plane;
- Pricing & Estimation Intelligence;
- Executive Commercial Mission Control;
- Customer Disappointment Prevention;
- Change Request & Scope Ledger;
- payment/fraud/reconciliation controls.

Existing authoritative ledgers remain sources of truth.


## Closed-loop autonomy extensions

The next layer completes the operating loop:

**UNDERSTAND → PLAN → EXECUTE → VERIFY → RECOVER → DELIVER → LEARN**

### P0 — Intent-to-Execution Compiler
Confirmed requirements and approved scope are compiled into bounded work packages, acceptance tests, dependencies, exclusions and immutable work-package evidence. Open discovery questions or missing acceptance criteria prevent compilation.

### P0 — Exception Autopilot
Approved non-Production failures may use bounded recovery playbooks. Retry budgets, cost budgets, loop detection, security signals, rollback evidence and consequential-impact boundaries decide whether the system continues or enters HUMAN_GATE.

### P0 — Evidence-Driven Completion Gate
BUILD_COMPLETE, QA_PASSED and DELIVERED are evidence states, not agent opinions. Required criteria, regression evidence, artifact digest and applicable customer acceptance must exist before completion can pass.

### P1 — Customer Dependency Automation
Uses Customer Onboarding/Kickoff and Customer Disappointment Prevention. Missing logo/content/access/approval produces CLIENT_ACTION_REQUIRED, clear itemised follow-up, and policy-based delivery-clock handling. Contact must use an approved channel and lawful basis.

### P1 — SLA & Deadline Guardian
Combines capacity and SLA evidence to detect trajectory risk early. It may reprioritise work only within approved policy. Contractual ETA changes remain governed review decisions.

### P1 — Autonomous Tool / Model Router
Selects only supported and certified execution paths that meet minimum quality/reliability gates, then optimises among eligible candidates using cost/latency evidence. It grants no Production authority.

### P1 — Learning & Optimization Loop
Verified delivery cost, rework, support burden and customer-acceptance evidence produce candidate improvements for Discovery, Pricing, Capability Registry and Capacity Policy. Learning never silently mutates policy.

### P1 — Commercial Recovery Engine
Supports bounded follow-up for PAYMENT_FAILED, QUOTATION_EXPIRING and CUSTOMER_INACTIVE states. It cannot charge, renew, mutate a contract or issue compensation automatically.

### P1 — Autonomous Change Impact Analyzer
Prepares scope, cost, time, dependency, risk and regression impact evidence, then hands off to the existing Change Request & Scope Ledger. It never approves the change itself.

### P0 — Global Kill Switch / Circuit Breaker
Security signals, cost spikes, repeated agent loops, systemic failures or stale hard-gate evidence open the circuit and stop affected autonomous actions. Recovery requires governed review.

These extensions compose existing LD modules rather than replacing their authoritative ledgers.
