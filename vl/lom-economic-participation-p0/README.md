# LOM Economic Participation Network P0 — Earn by Doing

Status: DEVELOPMENT / NON-PRODUCTION  
Tracking: Issue #424

## Purpose

Create a governed participation path where a person can earn from real, bounded work without turning LOM into a second HR, payroll, CRM, payment or accounting system.

P0 task type: `SCRIPT_POLISH` for low-risk short-video sales content.

Canonical flow:

`FUNDED_WORK -> READY -> ASSIGNED -> IN_PROGRESS -> SUBMITTED -> QA_CHECK -> PASS/REVISION/ESCALATE/REJECT -> PAYABLE_ENTITLEMENT -> HUMAN_PAYOUT_REVIEW -> RECONCILE -> CLOSED`

## Architecture

This capability owns only:
- microtask lifecycle;
- assignment eligibility;
- submission/revision records;
- deterministic task QA policy;
- worker reputation events;
- worker earnings entitlement records;
- shadow-pilot and scale-gate evidence.

It must reuse:
- LOM governance and authority boundaries;
- LOM independent QA/verification principles;
- LOM security/immune controls;
- existing authoritative payment and accounting adapters/ledgers;
- LundusLead/LD commercial demand and campaign systems where work originates.

It must not create:
- a second CRM;
- a second payment processor;
- a second accounting ledger;
- a payroll/HRMS engine;
- automatic production payout authority.

## P0 task contract

A `SCRIPT_POLISH` task receives:
- approved product/service facts;
- target audience;
- language;
- platform;
- objective;
- draft script;
- one approved CTA;
- funding allocation reference.

Worker may improve:
- wording;
- structure;
- hook;
- naturalness;
- clarity;
- CTA phrasing without changing the approved commercial meaning.

Worker may not invent:
- facts;
- prices;
- offers;
- testimonials;
- customer results;
- legal/compliance claims.

## QA

Score: 100 points.

- factual consistency: 30
- hook: 15
- clarity/readability: 15
- message focus: 10
- CTA: 10
- duration/format: 5
- tone/audience fit: 5
- policy/safety: 10

Decision:
- PASS: >=85, confidence >=0.80, no hard fail
- REVISION: 70-84 and no hard fail
- ESCALATE: uncertainty, factual conflict, low confidence, or sensitive issue
- REJECT: fabricated claim, severe policy violation, or score <50

Maximum revisions: 2.

## Economic controls

No valid funding reserve -> no paid task.  
No PASS -> no payable entitlement.  
No unique task entitlement -> no payout review.  
No provider/accounting reconciliation -> no CLOSED financial state.

This P0 emits an earning entitlement only. Actual payout remains through an existing payment adapter and a HUMAN_ONLY approval boundary.

## Worker progression

Starter -> Verified -> Specialist -> Senior

Reputation derives from evidence-backed events:
- accepted quality;
- reliability;
- revision rate;
- integrity;
- specialization;
- completion timeliness.

One minor failure must not cause disproportionate reputation loss. Fraud/security events are reviewed separately.

## Pilot

Shadow pilot first, using synthetic tasks only:
- Batch 1: 10
- Batch 2: 20
- Batch 3: 30
- Batch 4: 40

Live scale is forbidden until a human approves the pilot after reviewing:
- Quality
- Economics
- Operations
- Trust

Hard stops:
- duplicate payable entitlement;
- unfunded payable entitlement;
- unauthorized state mutation;
- material fabricated claim incorrectly passing;
- private data leak;
- accounting/payment reconciliation mismatch.

Synthetic evidence must never be represented as real customer, revenue or worker evidence.


## Base refresh

Refreshed against current `main` on 2026-09-29 before Digital Nation dependency review. This note does not grant merge, Production, payout, or live-pilot authority.
