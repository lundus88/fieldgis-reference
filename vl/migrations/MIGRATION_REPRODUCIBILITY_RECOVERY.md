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

## Governing rule

Historical migrations that were already used against production are immutable for recovery purposes. Do not edit them in place merely to make a new branch pass. Do not inject fake certification evidence, fake approvals, fake deployments, or fake health timestamps.

## Canonical recovery path

1. Generate a canonical schema snapshot from the linked production project using the supported Supabase schema-pull workflow (`supabase db pull --linked`) in an authenticated operator environment.
2. Review the generated snapshot against the current production schema before accepting it as baseline evidence.
3. Compare local and remote migration history with `supabase migration list`.
4. Use migration-history repair only as a tracking correction when the database schema is already proven to match. History repair must not be used to claim that SQL ran when schema parity has not been demonstrated.
5. Establish a fresh-data baseline for future environments so replay does not require production-only historical rows.
6. Recreate a data-less DEV branch from scratch and require the full migration/bootstrap path to finish without manual DDL scaffolding.
7. Run Supabase security and performance advisors.
8. Re-run the operational reconciliation and certification-health freshness regression suite.
9. Verify production read-only: no approval, deployment, factory run, workflow, or certification-health row changed as a side effect of recovery work.

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
