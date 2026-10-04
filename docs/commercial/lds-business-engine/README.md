# LUNDUS Business Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

## Purpose

Consolidate LD reusable commercial capabilities into one governed business engine instead of creating duplicate CRM, quotation, payment, delivery, QA or customer-management systems for every vertical.

## Architecture

LOM Intelligence
→ Business Orchestrator
→ LUNDUS Business Engine
→ Industry Pack
→ existing Ready Business Kit / Delivery Factory / QA
→ Preview / UAT
→ Human Production Gate

## Core capability boundary

The engine composes existing LD capabilities such as AUTH, CUSTOMER_DB, LEAD_CRM, QUOTATION, ORDER, PAYMENT, INVOICE, RECEIPT, PROJECT_STATUS, FILE_UPLOAD, PDF_GENERATOR, NOTIFICATION, APPROVAL_WORKFLOW, AUDIT_EVIDENCE and AI_ASSISTANT.

It is an orchestration and policy-composition layer only. Capability names in this engine are references to the owning system; they are not permission to create a second database, ledger, renderer or workflow authority.

Canonical ownership:
- **LundusLead** remains system of record for lead/CRM, marketing, qualification and follow-up.
- **Golden Transaction** remains authoritative for quotation and sale controls.
- **Payment, accounting, booking, WhatsApp and email** remain adapters/integration surfaces owned by their existing boundaries.
- **Professional Service Website Engine in LundusLead** is the canonical LD website runtime.
- **LD Ready Business Kit** is compatibility/reference only and must not be extended into a second website runtime.
- **Delivery Factory, QA, Production release governance and human authority gates** retain their existing authority.

The Business Engine must not persist authoritative duplicate lead, quotation, sale, payment, invoice or receipt state when an owning system already exists.

## Canonical commercial lifecycle

The lifecycle below is an orchestration view over authoritative systems, not a second transaction ledger:

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
→ SUPPORT_ACTIVE / CLOSED

Each state transition must resolve to the current owning system and reuse its existing evidence, approval and audit boundary.

## Industry Pack contract

Each Industry Pack declares:
- pack identity and vertical;
- reusable capabilities required;
- business entities;
- workflows;
- human gates;
- vertical-specific UI/data vocabulary.

An Industry Pack is configuration and bounded domain logic. It must not introduce duplicate generic engines where an existing LD capability already owns that function.

## Reference implementation

Property / Broker Edition is the first reference implementation.

Flow:
Owner
→ Listing
→ Verification / evidence
→ Buyer lead
→ Matching
→ Viewing
→ Negotiation / offer
→ Deal
→ Delivery / support

The Property Pack does not claim access to JTU, PBT, land-office or other government databases. Professional/legal/cadastral verification remains outside automated authority unless separately and lawfully integrated.

## Governance

Production deployment, live customer charging, customer commitment, privilege widening and destructive Production actions remain HUMAN_ONLY.

This package is not Production authority. It is a development consolidation layer.

## Platform Foundation P0

The next bounded layer adds:
- multi-tenant organisation configuration;
- package entitlement enforcement;
- deterministic Industry Pack registry;
- capability ownership resolution using REUSE_BEFORE_BUILD.

This layer remains DEVELOPMENT / NON-PRODUCTION and does not create Production database authority, billing authority or deployment authority.

See `PLATFORM_FOUNDATION_P0.md`.

## Business Engine P1

P1 adds a governed integration layer over existing specialist systems rather than creating replacements.

Flow:

Tenant / Organisation
→ Entitlement
→ Verified Membership
→ Business Engine P1 Integration Plan
→ Existing Client Portal / Delivery Factory / Pricing / Profitability / Mission Control
→ Existing Human Gates

P1 grants no new Production, live-charging, final-pricing or privilege authority.

See `BUSINESS_ENGINE_P1_INTEGRATION.md`.
