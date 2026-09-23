# LD FinanceBridge — Provider Route Evidence Runbook

Status: DEVELOPMENT / NON-PRODUCTION

## Purpose

This runbook moves FinanceBridge from generic provider selection to a controlled selected-provider sandbox integration without putting provider branding or secrets into the public LD core.

## Evidence required for every route

For each required operation, capture privately:

- canonical FinanceBridge operation name;
- exact HTTP method;
- exact staging path;
- request schema snapshot and SHA-256 digest;
- response schema snapshot and SHA-256 digest;
- authorised source reference;
- verifier identity;
- verification timestamp with timezone;
- evidence that the route is staging/test only.

Required P1 operations:

- upsert_customer
- create_invoice
- record_payment
- submit_einvoice
- get_einvoice_status
- create_receipt_reference
- reconcile

## Fail-closed rule

A route is not considered verified merely because:
- a marketing page says an API exists;
- a browser request returns HTTP 200;
- a path looks conventional;
- a provider acknowledgement is returned;
- a field name appears in an example.

The method, path, request/response schema and business semantics must all be verified.

## Private provider profile

Real provider identity, credentials, account identifiers and support references belong outside the public repository in authorised runtime/private evidence.

Do not commit:
- access tokens;
- secret keys;
- tenant/company secrets;
- production URLs tied to live credentials;
- customer accounting identifiers;
- MyInvois credentials.

## Gate sequence

Provider selected privately
→ sandbox credentials issued
→ transport/auth verified
→ route evidence complete
→ FinanceBridge preflight PASS
→ controlled sandbox Golden Transaction
→ reconciliation evidence reviewed
→ Production readiness review
→ explicit human Production approval

Production remains HOLD throughout P1.
