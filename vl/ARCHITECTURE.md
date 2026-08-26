# VL Automated Software Factory

The authoritative lifecycle is:

`Natural language → Compiler → App Spec approval → Builder router → staging Factory Run → GitHub OIDC runner → immutable artifact + SHA256 → Release Validator → technical certification → explicit human production approval → adapter promotion → post-deploy verification → deployed or rollback`.

Production approval is never autonomous. A technically certified release remains production-locked until an owner/admin calls the governed approval API. Approval must atomically pass `human_production_approval`, release `production_lock`, create one promotion job (enforced by `unique(deployment_id)`), and record the actor. Runners authenticate with GitHub OIDC; callbacks require the current unexpired lease token.

## Authoritative control-plane objects

- `public.app_specs`, `public.factory_runs`, `private.runner_jobs`
- `public.factory_artifacts`, `public.release_gates`, `public.deployments`, `public.approvals`
- `private.release_validation_jobs`, `private.production_promotion_jobs`
- `private.production_adapter_registry` and service-role view `public.production_adapter_status`
- Service-role command-centre view `public.vl_factory_status`
- `public.claim_vrs_runner_job` / `public.complete_vrs_runner_job`
- `public.claim_vrs_release_job` / `public.complete_vrs_release_job`
- `public.approve_vrs_production_release` / `public.reject_vrs_production_release`
- `public.claim_vrs_production_job` / `public.complete_vrs_production_job`

Workflows are `.github/workflows/vl-factory-runner.yml`, `vl-release-validator.yml`, and `vl-production-promoter.yml`.

## Production adapter contract

Every adapter declares configuration state, target type, required credentials, deployment, rollback, and health-check capabilities. Unconfigured adapters return `BLOCKED/UNCONFIGURED`; provider acceptance alone is never `deployed`.

- Mobile: reuse the exact GitHub Actions artifact, verify SHA256, publish immutable Android artifact, verify release metadata.
- Web/PWA/GIS: promote a prebuilt/previously validated Vercel deployment; verify HTTP reachability, boot, critical assets, plus PWA or MapLibre contracts. Requires Vercel credentials and target IDs.
- API: deploy a versioned Supabase Edge Function artifact, then verify health, JWT behavior, and response contract. Requires target credentials and function name.

Rollback always points to a prior successful certified artifact/deployment. It is appended to the audit trail and never deletes release history.

## State mapping

Existing constraints are reused: `certified` represents awaiting human approval; `approved` means the human gate passed and promotion is queued; `deploying`, `deployed`, `failed`, and `rolled_back` represent provider execution. Queue states distinguish `queued`, `leased`, `blocked`, `succeeded`, `failed`, and `cancelled`. The certificate and audit log preserve finer-grained verification and rollback metadata.

The system fails closed when evidence, credentials, target configuration, artifact identity, health verification, or a current lease is absent. It must never write PASS/deployed based on assumed evidence.
