# LD FinanceBridge P0

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

LD FinanceBridge is the vendor-neutral accounting and e-Invoice integration boundary for LUNDUS DIGITAL SYSTEMS (LD).

Its purpose is to prevent vendor lock-in and keep provider identity out of LD product branding.

Provider selection is runtime configuration, not business logic and not customer-facing branding.

## Canonical flow

Lead
→ Order
→ Human-approved Quotation
→ Contract / digital acceptance
→ Authoritative payment reconciliation
→ Commercial Invoice
→ LD FinanceBridge
→ Selected accounting/e-Invoice provider
→ validated compliance evidence
→ Receipt
→ Delivery
→ Accounting reconciliation

FinanceBridge never treats a browser redirect, client claim, invoice draft or provider acknowledgement as proof of payment or tax validation.

## Architectural boundary

LD remains authoritative for:
- customer and organisation identity;
- order and scope;
- approved quotation;
- payment state;
- delivery state;
- audit/evidence references.

The selected accounting provider is authoritative only for provider-side accounting/compliance records explicitly returned by that provider.

No provider may silently mutate LD commercial state.

## Provider-neutral connector contract

A provider connector may implement:
- `health()`
- `upsert_customer()`
- `create_invoice()`
- `submit_einvoice()`
- `get_einvoice_status()`
- `record_payment()`
- `create_receipt_reference()`
- `reconcile()`

All mutations require an idempotency key and deterministic evidence.

Provider-specific names, endpoints, tenant headers and credentials are deployment/runtime details. They are not LD product names and should not appear in public-facing LD customer UI.

## FinanceBridge sandbox binding

Public source code contains only a provider-neutral staging contract.

Runtime configuration supplies:
- sandbox base URL;
- access token;
- optional tenant/company header and key;
- documented provider rate limit.

Exact provider route paths and payload schemas remain unverified until independently confirmed against authorised documentation or sandbox evidence.

Current state:

`FINANCEBRIDGE_SANDBOX_BINDING = HOLD`

Reason:

`PROVIDER_ROUTE_CAPABILITY_VERIFICATION_REQUIRED`

The P0 request builder performs **no network calls** and rejects Production environment selection.

See:
- `PROVIDER_SANDBOX_REQUEST.md`
- `provider_capabilities.json`
- `financebridge_binding.py`
- `provider_sandbox_gate.py`

## Naming policy

**LD FinanceBridge** is the LD-owned subsystem name.

Third-party provider names may be used only when operationally necessary inside authorised private configuration, procurement/support correspondence, or evidence identifying the actual external service used.

They must not become:
- LD product names;
- LD module branding;
- customer-facing feature names;
- copied marketing language;
- claims of affiliation or ownership.

## Human gates

Human approval remains mandatory for:
- quotation/pricing commitment;
- exceptional refund or credit note;
- tax-classification override;
- invoice/e-Invoice failure after bounded retries;
- fraud/payment exception;
- high-value or material manual accounting adjustment;
- Production credential activation;
- Production deployment/promotion.

Routine provider synchronization may be autonomous after required evidence passes.

## Golden Transaction acceptance

The P0 Golden Transaction must prove:

1. approved quotation exists;
2. payment is authoritatively reconciled;
3. invoice amount/order/customer match;
4. accounting invoice is created idempotently;
5. e-Invoice submission occurs only when provider capability is verified;
6. validated evidence is required before claiming tax e-Invoice status;
7. receipt reference is issued only after paid + reconciled state;
8. delivery remains downstream of valid commercial evidence;
9. replay does not create duplicate invoice/payment/receipt records;
10. mismatches and unverified provider capabilities fail closed.

The deterministic provider-neutral Golden Transaction already covers the adapter contract.

The next proof is a **selected-provider sandbox Golden Transaction** after authorised credentials and exact route verification are available.

## Production gate

`ACCOUNTING_PRODUCTION_READY = HOLD`

It may change only after:
- authorised sandbox credentials are configured outside the repo;
- selected-provider capability matrix is verified;
- end-to-end sandbox Golden Transaction passes;
- webhook/callback authenticity is validated where applicable;
- duplicate/replay tests pass;
- provider outage and retry tests pass;
- tax/e-Invoice status semantics are verified;
- reconciliation evidence is reviewable;
- explicit human Production approval is recorded.

This module does not activate billing, tax submission, Production credentials or Production deployment.
