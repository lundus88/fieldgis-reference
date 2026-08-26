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

`private.production_deployment_verifications` stores individual post-deploy checks. A promotion callback cannot mark a deployment `deployed` unless its immutable SHA matches, `post_deploy_verification` is `PASS`, every supplied check passes, and non-mobile adapters provide a provider deployment reference. `private.production_rollback_audits` preserves deterministic rollback requests and their outcomes. `public.request_vrs_production_rollback` requires an authenticated project owner/admin and blocks unknown or uncertified targets.

## State mapping

Existing constraints are reused: `certified` represents awaiting human approval; `approved` means the human gate passed and promotion is queued; `deploying`, `deployed`, `failed`, and `rolled_back` represent provider execution. Queue states distinguish `queued`, `leased`, `blocked`, `succeeded`, `failed`, and `cancelled`. The certificate and audit log preserve finer-grained verification and rollback metadata.

The system fails closed when evidence, credentials, target configuration, artifact identity, health verification, or a current lease is absent. It must never write PASS/deployed based on assumed evidence.

## Controlled API staging evidence

Factory run `331a31a4-2eac-41c8-a2a2-7bc2544bc910` produced API artifact SHA256 `5b6b304e1aceb7cc0cacd5834c7e6fbc57e76effc4222ee16b36ef8622bbdee6` in GitHub Actions run `32917179571`. Its generated `api/index.ts` was deployed unchanged to JWT-protected staging function `vl-api-staging-331a31a4`, provider function id `96ec84df-5780-4507-881b-576f40f3c2f5`, version `2`. Provider status was `ACTIVE`; unauthenticated invocation returned `401`, and authenticated invocation returned HTTP `200` with `{"ok":true,"service":"VL API Builder Smoke"}`.

This is staging evidence, not a production release or technical production certification. The `api-service-v1` production adapter remains `UNCONFIGURED` until an explicit target/function mapping and GitHub secrets are authorized. Rollback execution is correspondingly blocked until a previous known-good certified provider version exists; the audit/request path is implemented and fails closed.
