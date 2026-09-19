# LUNDUS DIGITAL SYSTEMS — Pre-Launch Revenue Gate P0

Status date: 2026-09-18
Authority: HUMAN-GATED
Production payment: BLOCKED until licence readiness + explicit approval

## 1. Launch objective
Prove one complete Commercial Golden Transaction:
Visitor -> offer -> order/quote -> checkout -> provider/backend payment verification -> notification -> CRM/order record -> fulfilment -> receipt/invoice -> close.

## 2. Mandatory gates
- [ ] LICENCE_READY
- [ ] OFFER_LOCKED
- [ ] COMMERCIAL_SURFACE_READY
- [ ] LEGAL_TRUST_READY
- [ ] PAYMENT_PRODUCTION_READY
- [ ] GOLDEN_TRANSACTION_PASS
- [ ] FULFILMENT_PASS
- [ ] SUPPORT_ROLLBACK_PASS
- [ ] SECURITY_QA_PASS
- [ ] MEASUREMENT_READY

Public payment remains HOLD if any mandatory gate is unresolved.

## 3. Current evidence
PASS:
- vrs-core ACTIVE_HEALTHY
- vl-api-production ACTIVE_HEALTHY
- public_portal
- public_onboarding
- payment_sandbox_e2e
- rollback baseline
- database_security latest gate
- web_compile_test
- pwa_runtime_contract

BLOCKED/FAIL:
- live_billing = BLOCKED
- offline_pwa_contract = FAIL
- production payment orders = 0

PENDING:
- gps_permission_e2e
- kml_csv_export_e2e
- mobile_gis_regression
- offline_capture_e2e
- offline_pwa_e2e

Deployment evidence:
- vl-gis-production = 0 deployments
- vl-pwa-production = 0 deployments
- fieldgis-reference has READY production deployment, but is not the dedicated LUNDUS DIGITAL SYSTEMS commercial surface.

Open remediation:
- PR #259 GIS preview evidence/public-readiness canary hardening
- PR #218 database security boundary hardening

## 4. Commercial website requirements
Minimum pages/surfaces:
1. Home
2. Products / Services
3. Pricing or Request Quotation
4. About / business identity
5. Contact / support
6. FAQ
7. Privacy Policy
8. Terms of Service
9. Refund / Cancellation Policy
10. Checkout / payment confirmation
11. Order status / acknowledgement

Homepage priority:
- clear problem/offer
- one primary CTA
- one secondary quotation CTA
- trust proof
- contact/support
- no internal VL/LOM technical complexity exposed as the primary proposition

## 5. Payment P0
Must prove:
- server/provider verified amount
- unique order ID
- idempotent webhook processing
- paid / pending / failed / cancelled states
- reconciliation path
- notification to operator
- customer acknowledgement
- no fulfilment from client-side redirect alone
- no public service-role/secret leakage
- manual refund/dispute SOP

## 6. Operations P0
Pipeline:
New Lead -> Qualified -> Quotation -> Awaiting Payment -> Paid -> In Progress -> Delivered -> Closed

Exception paths:
Refund / Dispute / Support / Payment Unknown / Manual Review

## 7. Controlled launch
Initial users: 5–10 invited users.
Public release requires:
- Commercial Golden Transaction PASS
- zero unresolved P0 launch blocker
- support and rollback path verified
- production payment reconciliation verified

## 8. Revenue architecture
- LOM: internal revenue operating system
- VL: governed software factory
- Customer-facing products/services: monetization surface
- LundusLead: lead/order follow-up pipeline where appropriate

## 9. Feature freeze
Until Golden Transaction #1:
Only accept changes that improve:
- conversion
- payment
- fulfilment
- support
- security
- reliability
- measurement

Non-critical feature expansion is deferred.

## 10. Human gates
No Production billing activation, Production deployment, production database mutation, protected-main merge, customer charging, or authority widening is authorized by this document.
