# LD Accounting Adapter P0

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

Provide a vendor-neutral accounting and e-Invoice boundary for LUNDUS DIGITAL SYSTEMS (LD) so the LD commercial core is not locked to one accounting vendor.

P0 candidate provider: **Bukku**.
Fallback provider family: SQL Accounting.
Future international/multi-currency provider family: Xero.

Provider selection is configuration, not business logic.

## Canonical flow

Lead
→ Order
→ Human-approved Quotation
→ Contract / digital acceptance
→ Authoritative payment reconciliation
→ Commercial Invoice
→ Accounting Adapter
→ e-Invoice compliance provider
→ validated e-Invoice evidence
→ Receipt
→ Delivery
→ Accounting reconciliation

The adapter never treats a browser redirect, client claim, invoice draft, or provider request acknowledgement as proof of payment or tax validation.

## Architectural boundary

LD remains authoritative for:
- customer and organisation identity;
- order and scope;
- approved quotation;
- payment state;
- delivery state;
- audit/evidence references.

The accounting provider is authoritative only for provider-side accounting/compliance records explicitly returned by that provider.

No provider may silently mutate LD commercial state.

## Required adapter operations

A conforming adapter exposes:
- `health()`
- `upsert_customer()`
- `create_invoice()`
- `submit_einvoice()`
- `get_einvoice_status()`
- `record_payment()`
- `create_receipt_reference()`
- `reconcile()`

All mutating operations require an idempotency key and return a deterministic evidence envelope.

## Bukku sandbox binding P0

The official Bukku developer documentation confirms the following integration contract:

- API access is enabled in Bukku under **Control Panel → Integrations**;
- authentication uses `Authorization: Bearer <AccessToken>`;
- the company is selected using the `Company-Subdomain` header;
- `Accept: application/json` is required;
- JSON requests use `Content-Type: application/json`;
- documented API rate limit: **600 requests/minute**;
- staging API server: `https://api.staging.bukku.dev`;
- Production API server: `https://api.bukku.my`;
- Bukku recommends requesting a staging account before Production integration.

The P0 binding therefore fixes only the documented transport/authentication contract.

It intentionally does **not** guess invoice, payment or MyInvois endpoint paths or payloads. Exact routes stay unverified until their method, path, schema and semantics are confirmed against authorised Bukku documentation or staging evidence.

Current state:

`BUKKU_SANDBOX_BINDING = HOLD`

Reason:

`BUKKU_ROUTE_CAPABILITY_VERIFICATION_REQUIRED`

The request builder performs **no network calls**. Production environment selection is rejected by the P0 runtime.

See:
- `BUKKU_SANDBOX_REQUEST.md`
- `bukku_capabilities.json`
- `bukku_binding.py`
- `bukku_sandbox_gate.py`

## P0 Bukku posture

Public Bukku materials confirm:
- Open API availability;
- LHDN e-Invoice support;
- MyInvois-related company/contact/product fields;
- standard, consolidated and self-billed e-Invoice workflows.

The integration does **not** claim automatic MyInvois API submission until the exact route and staging behaviour are verified.

Therefore:
- provider capability flags default to false;
- unverified capability returns HOLD;
- no live credentials are stored in this repository;
- no Production call is permitted.

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

Routine provider synchronization may be autonomous after all required evidence passes.

## Golden Transaction acceptance

The P0 Golden Transaction must prove:

1. approved quotation exists;
2. payment is authoritatively reconciled;
3. invoice amount/order/customer match;
4. accounting invoice is created idempotently;
5. e-Invoice submission is attempted only when provider capability is verified;
6. validated e-Invoice evidence is required before claiming tax e-Invoice status;
7. receipt reference is issued only after paid + reconciliation state;
8. delivery remains downstream of valid commercial evidence;
9. replay does not create duplicate invoice/payment/receipt records;
10. mismatches and unverified provider capabilities fail closed.

The deterministic fake-provider Golden Transaction already covers the provider-neutral contract.

The next proof is a **Bukku staging Golden Transaction**, which cannot run until Bukku provides authorised staging credentials and the exact routes are verified.

## Production gate

`ACCOUNTING_PRODUCTION_READY = HOLD`

It may change only after:
- authorised provider sandbox credentials are configured outside the repo;
- Bukku capability matrix is verified;
- end-to-end sandbox Golden Transaction passes;
- webhook/callback authenticity is validated where applicable;
- duplicate/replay tests pass;
- provider outage and retry tests pass;
- tax/e-Invoice status semantics are verified;
- reconciliation evidence is reviewable;
- explicit human Production approval is recorded.

This module does not activate billing, tax submission, Production credentials or Production deployment.
