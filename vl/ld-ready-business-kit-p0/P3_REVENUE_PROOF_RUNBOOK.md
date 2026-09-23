# LD Ready Business Kit P3 — Golden Revenue Proof Runbook

Status: PRE-ACTIVATION / NON-PRODUCTION
Tracking: Issue #376

## Objective

Prepare one evidence-complete real customer transaction without confusing engineering readiness with revenue.

Canonical chain:

**Qualified lead → Human-approved quotation → Customer acceptance → Controlled transaction authority → Provider payment → Signed webhook → Paid order → Delivery → Invoice/receipt → Reconciliation → Revenue proof**

## Current stop condition

The authoritative Activation Snapshot remains HOLD. In particular, the dedicated LD business phone is still pending verification.

Therefore P3 may prepare evidence structures and synthetic dry-runs, but must not activate live charging, create a live paid transaction, claim real revenue, bind Production, or authorize public launch.

## Before the first controlled paid Golden Revenue Transaction

Revalidate the authoritative commercial gate and current Activation Snapshot. Controlled transaction prerequisites must be current and PASS, including:
- business/licence evidence;
- legal trust, including verified dedicated business phone;
- commercial domain/origin readiness;
- live lead-intake configuration and authority;
- Production payment configuration and authority;
- webhook verification path;
- rollback/support path;
- separate explicit human authority for the one controlled transaction.

That authority is not public-launch authority.

## Evidence capture

For the first real customer, record immutable references for qualified lead, approved quotation, customer acceptance, controlled transaction human authority, provider payment, signed webhook, paid order, delivery, invoice/receipt, and reconciliation.

Amounts must match server-authoritative quotation/payment evidence. A browser redirect is never payment evidence.

## Unit economics

Capture evidence-backed marketing cost, delivery cost, payment fee, setup minutes, and support minutes.

Attributable revenue = verified payment - refund

Commercial contribution = attributable revenue - marketing cost - delivery cost - payment fee

Do not invent missing cost or time values.

## First-five experiment

Use first-five-prospect-experiment.json. The five slots start empty. Real outcomes are entered only from real evidence.

## FinanceBridge boundary

P3 does not replace LD FinanceBridge. Accounting/e-Invoice evidence remains governed by FinanceBridge and its separately verified provider integration.

## Synthetic dry-run rule

Synthetic fixtures may validate schemas and state transitions. They must always report real_revenue_proof = false.

Synthetic PASS means readiness PASS only, never revenue PASS.

## Success criterion

P3 engineering is complete when CI proves current live readiness correctly remains HOLD, synthetic dry-run cannot become real revenue proof, incomplete evidence and amount mismatches fail closed, complete real-evidence logic is deterministic, and real proof grants no public-launch authority.

Actual REAL_REVENUE_PROOF = PASS remains impossible until a real controlled transaction occurs after separate activation prerequisites and human authority are satisfied.
