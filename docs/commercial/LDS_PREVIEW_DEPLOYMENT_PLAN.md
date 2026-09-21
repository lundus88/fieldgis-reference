# LUNDUS DIGITAL SYSTEMS — Preview Deployment Plan

Status: NON-PRODUCTION
Purpose: prepare and, once safe tooling is available, deploy a dedicated Preview environment without touching any existing Production deployment.

## Human approval
Approval received on 2026-09-19 for:
- creating a dedicated isolated Vercel project;
- deploying the LDS commercial surface to Preview only.

This approval does **not** authorize:
- Production promotion;
- Production domain binding;
- Production secrets;
- live form submission;
- live checkout;
- real customer data;
- real customer charging.

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

## Execution status
CURRENT_PREVIEW_REFRESHED_STATIC_QA_PASS_VISUAL_RERUN_HOLD.

Verified currentness evidence on 21 September 2026:
- dedicated project binding: `prj_9areW7U50izhbz8yNrXK2r1YcJ1F` / `lundus-digital-systems-preview`;
- explicit project-scoped Vercel REST deployment path: PASS;
- deployed source SHA: `42b16dfb2a27e09b41cdf1ebbbd2c0dff02adb54`;
- canonical refreshed deployment: `dpl_EtpmqbwrL8G3rdRMgfxjTpBY9yhK`;
- deployment state: READY;
- Vercel API target: `null` / non-Production Preview;
- Production aliases: none;
- Preview project environment variables: none;
- commercial-surface contract: PASS;
- static/responsive surface QA: PASS;
- noindex + robots guard: PASS;
- direct Preview access remains behind Vercel SSO and emits `x-robots-tag: noindex`;
- later protected-main SHA `c784d6bdfa96ab31c5f8eb0e8f5a512fae0fb545` contains no commercial-path drift after the deployed source SHA.

A fresh rendered browser visual rerun is still HOLD because the available runtime could not obtain a browser binary. Historical V4 visual QA remains valid only as historical evidence and must not be treated as current deployment visual evidence.

Evidence manifest:
`docs/commercial/LDS_PREVIEW_CURRENTNESS_EVIDENCE_2026-09-21.json`

## Deployment procedure once a safe project-scoped mutation path is available
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
