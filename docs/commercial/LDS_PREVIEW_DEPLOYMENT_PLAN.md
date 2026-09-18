# LUNDUS DIGITAL SYSTEMS — Preview Deployment Plan

Status: NON-PRODUCTION
Purpose: prepare a safe Preview environment without touching any existing Production deployment.

## Why a dedicated Preview is required
Current Vercel evidence for the existing fieldgis-reference project shows only Production-target deployments. Therefore the LDS commercial surface must not be previewed by reusing that Production target.

## Proposed Preview isolation
- dedicated Vercel project name: lundus-digital-systems-preview
- source repository: lundus88/fieldgis-reference
- source branch for Preview: p0/lundus-digital-systems-commercial-surface
- root directory: commercial/lundus-digital-systems
- deployment target: preview only
- production domain: none
- custom commercial domain: none until verified
- indexing: blocked by page-level noindex + robots.txt
- live form submission: disabled
- live checkout: disabled
- Production payment secrets: absent
- customer data: prohibited
- real customer charging: prohibited

## Preview environment contract
Allowed:
- static HTML/CSS/JS
- anonymous test browsing
- 5–10 invited testers
- test/demo data only
- link/mobile/accessibility testing
- legal/trust copy review

Forbidden:
- Production Supabase service role
- Billplz Production API secret
- Resend Production API key
- Production webhook secrets
- real customer contact submission
- live billing
- Production domain alias
- search indexing

## Deployment procedure after human approval
1. Create a dedicated Vercel project separate from fieldgis-reference Production.
2. Set root directory to commercial/lundus-digital-systems.
3. Connect only the intended Preview branch.
4. Confirm there is no Production domain binding.
5. Confirm no Production secrets/environment variables exist.
6. Deploy as Preview.
7. Verify noindex/robots.
8. Run the static HTTP/surface QA suite.
9. Run tester journey from the Controlled Tester Pack.
10. Record immutable deployment ID and URL as evidence.
11. Do not promote to Production.

## Preview PASS criteria
- deployment target is preview;
- project is not fieldgis-reference Production;
- no Production domain;
- no Production secrets;
- no customer data;
- no live form submission;
- no live checkout;
- noindex + robots block indexing;
- all required pages load;
- mobile/static QA PASS;
- tester cohort remains controlled.

## Stop conditions
Abort Preview deployment if:
- tool/project scope is ambiguous;
- deployment target resolves to production;
- Production environment variables are inherited;
- custom Production domain is attached;
- any live payment/customer write path is enabled.

This document does not authorize creating the Vercel project or deploying it. Those remain separate human-gated actions.
