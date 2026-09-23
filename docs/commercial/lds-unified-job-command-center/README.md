# LD Unified Job Command Center P0

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: absorb the highest-value "all-in-one operations" pattern into LD without creating a second source of truth or weakening existing governance.

## Core idea

One project/job is represented by one composed operational view spanning the full commercial and delivery lifecycle.

Canonical lifecycle:

LEAD
→ DISCOVERY
→ QUALIFICATION
→ QUOTATION
→ APPROVAL
→ PAYMENT
→ PRODUCTION
→ QA_UAT
→ DELIVERY
→ ACCEPTANCE
→ INVOICE_EINVOICE
→ ACCOUNTING
→ SUPPORT
→ REPEAT_REFERRAL

The command center is an orchestration and visibility layer. Existing authoritative ledgers remain authoritative.

## High-value capabilities absorbed

### 1. Unified Job Command Center
Each job exposes:
- customer / organization;
- current lifecycle state;
- next action;
- owner / action mode;
- blocker reason;
- quotation / payment / invoice / receipt state;
- production / QA / UAT / delivery state;
- evidence freshness;
- support state;
- unit economics;
- retry / recovery state.

### 2. Client self-service integration
The existing Client Portal remains the customer-facing surface. It may consume the same composed job summary, while all state-changing actions remain separately gated, authenticated, idempotent and evidence-backed.

### 3. Event-driven progression
A verified event may propose the next lifecycle transition. Examples:
- quotation accepted → await authoritative payment reconciliation;
- payment reconciled → evaluate autonomous kickoff eligibility;
- QA passed → prepare customer UAT;
- customer accepted → prepare delivery;
- delivery evidenced → prepare invoice / accounting handoff.

Events do not become authority by themselves.

### 4. API / webhook boundary
External integrations must enter through signed, validated, idempotent adapters. Browser redirects and UI state are never authoritative evidence.

### 5. Agentic orchestration
LOM may plan, route and execute eligible non-Production work, but it must obey the existing policy-as-code, evidence, authority and circuit-breaker controls.

## Design principles

- one composed operational view, many authoritative source records;
- no duplicate truth;
- event-driven, fail-closed state transitions;
- evidence before "done";
- automation for standard work, human gates for consequential exceptions;
- signed webhook verification and replay protection;
- idempotency for every consequential transition;
- least privilege for all tools and credentials;
- no Production activation from this package.

## Relationship to existing LD modules

This package composes:
- Smart Client Discovery;
- Unified Commercial Control Plane;
- Autonomous Operations Layer;
- Client Portal;
- FinanceBridge / Accounting Adapter;
- payment reconciliation;
- QA / UAT / delivery evidence;
- support / renewal / referral modules;
- LOM Agentic OS.

It does not replace any of them.

## Safety boundary

Remain HUMAN_ONLY unless separately authorised:
- Production deployment / promotion;
- live charging activation;
- destructive Production data action;
- privilege elevation;
- material contract/scope exception;
- high-risk compliance decision;
- irreversible customer-impacting action without rollback evidence.

Global invariant:

**No lifecycle advance without valid evidence, legal transition, idempotency and the required authority.**
