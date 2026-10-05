# VL Operability Reconciliation

Status: proposed fail-closed repair contract. This branch does not deploy or mutate the live control plane.\n\nCurrent stabilization base: synchronized with `main` commit `714f4b43e1dadd7536026503ac0e59c21055873a`.

Repository context: visual preview enforcement from PR #141 is now merged to `main`; this operability patch remains independent and does not alter Factory visual-gate logic.

## Verified 2026-09-09 read-only findings

- `VL Unseen PWA Field Inspection`
  - factory run `cd2ae968-ccd4-4222-b140-ed463dc72fbb`: `validating`
  - workflow `ece3734f-1771-4de4-b9cc-ae709b107758`: `running`
- `VL Unseen PWA Equipment Handover`
  - factory run `2e07a4f8-a389-4882-99ac-f800a6179451`: `failed`
  - workflow `bc36298a-5ab3-4d5c-871a-73152bc7fca4`: `running`
- 22 factory runs are `awaiting_approval`.
- 21 approval rows are `pending`.
- All 22 awaiting-approval factory runs are staging-targeted and `production_locked=true`.
- One awaiting-approval run, `VL Golden API` / factory run `7e6abb39-0d19-4e3d-9bbb-2af7aa143c83`, has an existing deployment row bound to the logical `production` environment. It is therefore explicitly excluded from automatic stale approval disposal and requires manual audit.
- `public.vl_cert_health` reports source status `ok` but its authoritative timestamp is from 2026-08-25, so the signal is stale and must not be treated as current health.

## Verified 2026-10-04 certification provenance findings

Fresh read-only production inspection found that the legacy `public.vl_cert_health` row is still the same 2026-08-25 bootstrap-era signal and has no database trigger or repository writer currently binding it to the live certification engine.

The actual builder certification engine is active and evidence-backed:

- every builder whose `builder_registry.status='active'` has a latest certification decision of `certified`;
- active builders have score `1.0`, zero missing evidence and four distinct certification runs;
- each active builder has at least one complete fresh evidence set generated on 2026-10-03/04;
- fresh evidence sources resolve to GitHub Actions OIDC runs or certified release-gate URIs;
- the supporting factory runs are staging-targeted and production-locked.

This evidence does **not** authorize an ad-hoc timestamp refresh. It establishes that an authoritative health finalizer can be built on existing certification evidence without creating a duplicate certification engine.

## Verified 2026-10-05 certification phase closure — GREEN

The builder certification phase is formally closed as **GREEN** based on fresh evidence and current evaluator results after PR #480 merged.

- all five supported builders are `certified`: `web-react-v1`, `pwa-react-v1`, `mobile-flutter-v1`, `gis-web-v1`, and `api-service-v1`;
- every latest certification result has score `1.0` and zero missing evidence;
- `gis-web-v1` and `mobile-flutter-v1` each have six distinct complete certification runs under the official evaluator;
- GitHub Actions run `37156359095` completed both `gis-depth` and `mobile-depth` successfully, including Android emulator GPS/device E2E and evidence recording;
- PR #480 resolved the MapLibre worker bundling blocker and its relevant CI completed successfully;
- the supporting certification runs remain staging-targeted and `production_locked=true`.

**Closure status: GREEN.**

This closes the certification phase only. It does **not** authorize Production activation, promotion, deployment, broad public launch, or bypass of the existing human gate.

## Production activation readiness hardening — 2026-10-05

The certification phase is GREEN, but Production readiness remains separately governed.

- the reviewed candidate path adds an AAL2-only human authorization producer for certification-health finalization;
- the finalizer independently revalidates evidence digest, project scope, freshness, replay state and Production-authority exclusions;
- evidence older than the effective-health 30-minute window is rejected;
- selected evidence runs with actual Production authority/effect are rejected;
- forward DDL is materialized in `vl/migrations/20261004154500_cert_health_activation_hardening.sql`;
- reverse DDL is code-only and removes only the introduced functions/views/triggers;
- Supabase Auth currently has one verified MFA factor, but a live AAL2 operator session is still required at authorization time;
- backup freshness and tested restore evidence remain required before any Production DDL gate;
- `vl_cert_health` remains stale until a genuine fresh certification window is finalized through the reviewed human-gated path.

No Production approval, promotion, deployment or builder activation is authorized by this hardening.

## Repair principles

1. Historical reconciliation is terminal-only: `failed` or `cancelled`.
2. It must never create `certified`, `succeeded`, `approved`, `deploying` or `deployed` state.
3. Any factory run with a production-environment deployment row is excluded from automated reconciliation/expiry.
4. Production-targeted or production-unlocked factory runs are excluded.
5. Every permitted mutation requires row locking, bounded age, explicit rationale and machine-readable runner identity.
6. Reconciliation is idempotent.
7. Pending approvals are never bulk-approved. Expiry is an explicit per-approval governed disposition.
8. A stale health timestamp is reported as `stale`; the monitor does not fake a new `updated_at` value.
9. Production approval, production promotion and production deployment authority remain unchanged.
10. Certification health may be finalized only from fresh complete certification evidence generated after an explicit run start.
11. Re-evaluating historical evidence is not sufficient to refresh health.
12. A blocked certification finalization must leave `public.vl_cert_health` untouched and emit an audit record.
13. A successful finalization may update only the existing health row; it may not create certification evidence/results or mutate Factory lifecycle state.
14. Certification-health finalization requires a separate AAL2 human authorization audit record that is cryptographically bound to the exact selected evidence set by SHA-256 digest.

## Files

- `reconciliation_contract.sql`: candidate database contract for governed orphan reconciliation and explicit stale-approval expiry.
- `health_freshness_contract.sql`: read-only effective-health calculation that converts old signals to `stale`.
- `cert_health_writer_contract.sql`: candidate evidence-bound finalizer that may refresh the existing health row only after every active builder has a fresh complete certification run.
- `check_operational_contract.py`: CI governance checks preventing positive lifecycle/deployment mutations, synthetic certification evidence and unsafe health refreshes from entering this patch.

## Certification-health finalization gate

The writer contract requires all of the following before `vl_cert_health.updated_at` can change:

1. `run_started_at` is explicit and not in the future.
2. The caller supplies an explicit bounded maximum run age; there is no silent/default freshness policy.
3. Every active builder has an active certification policy.
4. Every active builder has a certification result evaluated after `run_started_at`.
5. That result is `certified`, meets policy score/depth and has no missing evidence.
6. Every active builder has one complete PASS evidence set created after `run_started_at` within a single factory run.
7. The evidence rows have non-empty provenance URIs.
8. The evidence-producing factory run is `staging`, `awaiting_approval` and `production_locked=true`.
9. The selected evidence set is canonicalized and SHA-256 digested.
10. A separate `vl.cert_health_finalization_authorized` audit record must bind the same `run_started_at`, `max_run_age_seconds` and `evidence_digest`.
11. The authorization must be AAL2, created after the selected evidence, no older than 15 minutes, and performed by an owner/admin who covers every selected evidence project.
12. One authorization record may be consumed only once; replay is fail-closed.
13. The health timestamp is the oldest selected builder `last_evidence_at`, not the wall-clock finalization time.
14. Failure records an audit event and leaves the old health row untouched.

This finalizer is not a certification producer. It only summarizes evidence produced by the existing certification engine.

## Required rollout gates

Before runtime activation:

1. Create an isolated Supabase development branch using the normal project tooling and cost approval process.
2. Materialize the SQL as a proper Supabase migration using the project migration workflow; do not ad-hoc apply this candidate SQL to live `vrs-core`.
3. Run database tests covering the two historical state pairs, idempotency, under-age rejection, production-deployment rejection and stale approval expiry.
4. For certification health, test no-active-policy, stale run, incomplete evidence, non-certified result, non-staging run, unlocked run, fabricated authorization ID, wrong evidence digest, wrong AAL, stale authorization, authorization-before-evidence, scope mismatch, replay, and successful fresh evidence cases.
5. Run Supabase security and performance advisors.
6. Add an OIDC-authenticated or equivalently governed **human-triggered** finalization path; the DB function itself must not become a general public RPC.
7. Run a dry-run inventory and require zero production-environment candidates.
8. Reconcile only the explicitly reviewed historical IDs.
9. Re-query the live control plane read-only and confirm no affected row gained production authority.
10. Only after the writer is human-reviewed, merged and deployed may a genuine fresh certification finalization update `vl_cert_health`.

## Non-goals

- No production approval.
- No production promotion.
- No production deployment.
- No synthetic PASS evidence.
- No certification evidence/result creation by the health writer.
- No builder activation.
- No weakening of certified-deployment or immutable provenance requirements.
