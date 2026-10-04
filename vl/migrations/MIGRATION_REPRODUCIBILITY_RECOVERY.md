# VL Migration Reproducibility Recovery

Status: P0 recovery contract. Repository-only. No production database mutation is authorized by this document.

## Verified problem

A fresh, data-less Supabase development branch created from `vrs-core` on 2026-09-10 could not replay the complete remote migration history. The first observed blocker was `20260826024508_harden_production_promotion_rpcs`, which referenced production-promotion RPCs that already existed in production but were not reproducible from the preceding recorded migration chain.

Additional replay gaps were verified for:

- `private.production_adapter_registry`
- `private.production_promotion_jobs`
- `private.builder_release_gate_profiles`
- `private.release_validation_jobs`
- `private.auto_prepare_release_candidate()`
- `public.vl_cert_health`

The replay was safely advanced in an isolated DEV branch with temporary fail-closed schema scaffolding only. No production data or authority was copied. The branch was deleted after testing.

A second class of blocker is historical-data dependence. `20260829_raise_web_pwa_certification_depth.sql` and `20260829_builder_certification_depth_3.sql` require historical certification evidence to already prove the requested depth. A data-less branch cannot satisfy that condition by design. Synthetic PASS evidence is prohibited.


## Read-only refresh — 2026-10-04

A fresh read-only metadata fingerprint of `vrs-core` shows that the 2026-09-10 snapshot is no longer current:

- migration history: **174** entries (was 166);
- latest migration: `20261004003624` (was `20260901034112`);
- functions: **128** (was 122);
- columns: **821** (was 815);
- constraints: **346** (unchanged);
- indexes: **215** (unchanged);
- policies: **88** (unchanged).

This metadata refresh is evidence of drift only. It is **not** a canonical schema dump and must not be used to authorize migration-history repair. The authoritative operator step is the manual, read-only `VL Schema Capture Evidence` workflow using the project IPv4 Transaction Pooler with `db dump --db-url` + `migration fetch --db-url`.

An isolated DEV validation on 2026-10-04 reproduced the known gap: `public.vl_cert_health` exists in Production but is absent from the native fresh replay path. Canonical baseline recovery then achieved exact schema and migration-history parity twice on a data-less DEV branch, without synthetic PASS evidence. Issue #153 is therefore technically GREEN candidate, pending repository merge of PR #474. PR #472 has runtime-proof PASS on DEV but remains HOLD until #474 is merged and #472 is refreshed against `main`.

## Governing rule

Historical migrations that were already used against production are immutable for recovery purposes. Do not edit them in place merely to make a new branch pass. Do not inject fake certification evidence, fake approvals, fake deployments, or fake health timestamps.

## Canonical recovery path

1. Run the manual read-only `VL Schema Capture Evidence` workflow through the IPv4 Transaction Pooler and preserve the schema + migration evidence with checksums.
2. Review the captured schema against current Production metadata before accepting it as canonical baseline evidence.
3. On a fresh data-less DEV branch, apply the canonical schema baseline through the repository-controlled bootstrap path.
4. Prove exact schema parity before synchronizing migration tracking; tracking synchronization must never stand in for schema creation.
5. Synchronize DEV-only migration tracking to the exact authoritative 174-row Production history only after parity is proven.
6. Recreate/reset the data-less DEV branch and repeat the bootstrap path to prove deterministic recovery without manual DDL scaffolding.
7. Run Supabase security and performance advisors.
8. Re-run the operational reconciliation and certification-health freshness/finalizer regression suite.
9. Verify Production read-only: no approval, deployment, factory run, workflow, candidate function, audit row, or certification-health row changed as a side effect of recovery work.

## Certification-data migration rule

Historical certification-depth migrations may remain fail-closed in the legacy chain. They must never be made replayable by seeding synthetic `builder_certification_evidence` with PASS status.

For the canonical baseline path, certification state must be treated as runtime evidence, not schema bootstrap material. A fresh environment may start with no certification evidence and therefore with builders unproven until new evidence is generated through the normal certification workflow.

## Exit criteria

Migration Reproducibility P0 is GREEN only when all are true:

- canonical production schema snapshot exists in version control;
- local/remote migration history differences are explicitly reconciled;
- fresh data-less DEV creation succeeds without manual DDL scaffolding;
- no synthetic positive certification evidence exists in bootstrap/seed/recovery paths;
- security and performance advisors have been reviewed;
- operational reconciliation tests PASS;
- certification-health freshness tests PASS;
- read-only production verification shows zero unintended mutation.

Until then, production activation of the operational reconciliation contract remains HOLD.


## Validation result — 2026-10-04

All technical exit criteria above were demonstrated on an isolated data-less DEV branch and recorded in `DEV_REPLAY_EVIDENCE_2026-10-04.md`.

- canonical baseline: PASS
- repeatable bootstrap: PASS
- exact schema parity: PASS
- exact migration-history parity: PASS
- security/performance advisor review: PASS / INFO-only
- operational reconciliation regression: PASS
- certification-health fail-closed regression: PASS
- Production non-mutation verification: PASS
- temporary DEV branch: deleted after testing

Repository merge remains a human gate. Production activation remains HOLD.
