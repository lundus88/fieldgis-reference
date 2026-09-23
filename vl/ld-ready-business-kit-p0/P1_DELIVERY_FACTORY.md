# LD Ready Business Kit P1 — Delivery Factory

Status: DEVELOPMENT / NON-PRODUCTION

## Goal

Turn a validated onboarding submission into a repeatable internal delivery workspace.

Flow:

**Onboarding → Preview → Proposal Draft → Quotation Draft → Human Pricing Approval → Human Customer Release → Customer Acceptance Evidence → Delivery Prep**

## What P1 automates

- deterministic client project ID
- preview generation
- proposal draft
- quotation draft
- delivery workspace/checklist
- delivery manifest preparation
- evidence-bound state transitions

## What P1 does not automate

- final price
- discount
- customer commitment
- quotation release
- customer acceptance
- payment request
- Production publish

Those remain human/evidence gates.

## Pricing

The current package values are **reference values only** for internal validation.

No reference price becomes a customer price until a human explicitly approves an amount.

## P1 output

For each vertical fixture CI generates:

- preview HTML
- proposal JSON
- quotation JSON
- workspace JSON

This demonstrates that the same core can produce repeatable client delivery artifacts without building each customer from zero.
