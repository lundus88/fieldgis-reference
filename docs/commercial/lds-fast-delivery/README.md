# LD Fast Delivery System v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: make Lundus Digital delivery fast, visible, predictable and governed without weakening QA, security or human authority.

## Operating promise

- acknowledgement target: <= 1 business day
- initial scope/timeframe target: <= 2 business days when required customer inputs are available
- first visible value target: 48-72 hours for eligible work
- delivery estimates are scope-dependent, not guarantees
- blocked customer dependencies pause/rebaseline delivery dates
- production activation, payment activation, protected-main merge and consequential release remain separately human-approved

## Delivery lanes

### STANDARD
Default lane. Work enters the governed capacity queue and is scheduled according to priority, fit and available certified delivery capacity.

### FAST_TRACK
Optional premium lane. Allowed only when:
- scope is sufficiently bounded;
- dependencies are available;
- certified capacity is reserved;
- no required governance or QA gate is bypassed.

Fast-track changes priority/capacity allocation only. It never weakens testing, security, UAT or release authority.

## Project classes

- QUICK_AUTOMATION: target 3-7 business days
- STARTER_SYSTEM: target 1-3 weeks
- SEMI_CUSTOM: target 3-6 weeks
- COMPLEX: milestone-based

These are planning bands. The authoritative estimate belongs in the human-approved quotation/SOW.

## State machine

INTAKE
→ QUALIFIED
→ SCHEDULED
→ BUILDING
→ QA
→ UAT
→ DELIVERY
→ SUPPORT

Exception states:
- CLIENT_ACTION_REQUIRED
- AT_RISK
- BLOCKED
- HOLD

Only customer/human authority may issue final business acceptance. LOM may orchestrate UAT evidence but may not accept on the customer's behalf.

## Fast visible progress

Eligible projects should expose a demonstrable artifact early:
- wireframe/prototype;
- working workflow;
- configured starter module;
- sample dashboard;
- sandbox integration.

The artifact must be labelled preview/prototype when it is not production-ready.

## Reusable modules

Initial registry categories:
- authentication / role access
- dashboard / reporting
- quotation / order workflow
- CRM / customer records
- notifications
- file/document management
- approval workflow
- GIS / map surface
- AI-assisted workflow
- audit / activity log

A module being reusable does not imply it is certified for every project. Compatibility and security checks still apply.

## Capacity governance

The system must never start unlimited concurrent builds.

Each intake receives:
- complexity class;
- delivery lane;
- evidence completeness;
- dependency readiness;
- customer urgency;
- estimated effort points.

If active capacity is exhausted, the project remains SCHEDULED/WAITLIST rather than entering BUILDING.

## UAT

LOM may:
- generate UAT checklist;
- collect PASS/FAIL evidence;
- open remediation tickets;
- track re-test status;
- prepare an acceptance package.

Customer/human must:
- validate business workflow;
- approve/reject deliverables;
- provide final acceptance.

VL performs technical remediation and regression testing.

## Online-only service model

Standard delivery and support are asynchronous and online-first:
- client portal/ticket;
- email;
- chat;
- screenshots/logs;
- shared documents;
- recorded screen evidence when useful.

No onsite meeting or video call is required for standard service.

## Evidence

Every transition into QA, UAT, DELIVERY and SUPPORT should have evidence references. Claims such as "complete", "accepted" or "ready" must not be inferred from elapsed time alone.
