# LUNDUS DIGITAL SYSTEMS — Preview Deployment Plan

Status: **NON-PRODUCTION / PREVIEW V4 READY**
Rebaselined: **2026-09-26**

Purpose: record the current isolated Preview state for the LDS commercial surface without granting Production authority.

## Current authoritative Preview evidence

The dedicated Preview environment has already been created and validated.

- Vercel project: `lundus-digital-systems-preview`
- project ID: `prj_9areW7U50izhbz8yNrXK2r1YcJ1F`
- Preview deployment ID: `dpl_F4rugJSSdfWMmUzb6T2ShGSRnZCJ`
- commercial surface source SHA: `57d4fe20c89e6cffc94047e7f6f7b4da4f4f538f`
- target: `preview`
- Preview state: `READY`
- visual QA: `PASS`
- workflow QA: `PASS`
- Production aliases: none authorised
- Production promotion: not authorised

The earlier `AUTHORIZED_PENDING_SAFE_MUTATION_PATH` state is historical and has been superseded by the completed isolated Preview deployment evidence above.

## Human approval scope

Approval covered:
- creating a dedicated isolated Vercel project;
- deploying the LDS commercial surface to Preview only.

It does **not** authorize:
- Production promotion;
- Production domain binding;
- Production secrets;
- live public lead intake;
- live checkout;
- real customer charging;
- DNS mutation;
- public launch.

## Preview isolation contract

Allowed:
- static HTML/CSS/JS;
- anonymous/invited test browsing;
- 5–10 controlled testers;
- test/demo data only;
- link/mobile/accessibility testing;
- legal/trust copy review.

Forbidden:
- Production Supabase service-role exposure;
- Billplz Production secret exposure;
- Resend Production secret exposure;
- Production webhook-secret exposure;
- real customer charging;
- public Production lead intake;
- Production domain alias without separate approval;
- Production promotion;
- search indexing where the Preview contract requires noindex.

## Current Preview PASS criteria

Verified:
- dedicated Preview project exists;
- deployment target is Preview;
- project is isolated from the existing fieldgis-reference Production target;
- visual QA is PASS;
- workflow QA is PASS;
- no Production promotion authority is granted by Preview readiness.

Still separate gates:
- `LEGAL_TRUST_READY`;
- `LIVE_LEAD_INTAKE`;
- `PAYMENT_PRODUCTION_READY`;
- `GOLDEN_TRANSACTION_PASS`;
- `DNS_PRODUCTION_BINDING`;
- Activation Snapshot;
- public payment activation;
- public launch.

## Evidence authority rule

Preview readiness is evidence only.

A READY Preview must never be interpreted as:
- Production readiness;
- payment-provider readiness;
- live lead-intake authority;
- public-launch authority;
- approval to bind `lundusdigital.com` to Production.

The final commercial activation gate and a fresh Activation Snapshot remain authoritative for Production decisions.

## Stop conditions

Return to HOLD and revalidate Preview evidence if:
- the exact Preview deployment changes materially;
- Production environment variables are introduced;
- a Production domain alias is attached without authority;
- live payment/customer-write paths are enabled;
- material legal/contact/commercial disclosure drift is detected.
