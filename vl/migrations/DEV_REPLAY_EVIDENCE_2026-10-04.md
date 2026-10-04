# VL Fresh DEV Replay Evidence — 2026-10-04

Status: P0 recovery validation evidence. Production remained read-only throughout.

## Target

- Production project: `vrs-core` / `wczelfmnqpgzfdszxubl`
- Ephemeral DEV branch: `vl-repro-baseline-20261004`
- DEV project ref: `inhmmupeselvtwlblsgn`
- DEV branch id: `bb455f15-0bcf-48f6-8dab-6009be985fde`
- Branch cost rate confirmed before creation: USD 0.01344/hour
- DEV branch created data-less.

## Native fresh replay finding

Fresh Supabase branch creation/reset reproduced the legacy-chain failure deterministically:

- applied migrations before failure: **48**
- last successfully applied migration: `20260826010511_fix_gis_source_seed_maplibre_import`
- `public.vl_cert_health`: absent
- schema fingerprint at the partial replay:
  - functions 33
  - columns 349
  - constraints 159
  - indexes 101
  - policies 81

A second branch reset reproduced the same condition and reported platform status `MIGRATIONS_FAILED`.

This proves the legacy 174-migration chain is not a complete fresh-environment bootstrap source.

## Canonical baseline replay — pass 1

The application schemas `public` / `private` were reset on DEV only after verifying no extension-owned objects existed there.

The reviewed schema baseline was applied, then the exact 174 Production migration-tracking rows were copied read-only from Production into DEV only after schema parity had been proven.

Exact DEV/Production parity was achieved:

- migration count: **174 / 174**
- first migration: `20260825085858`
- last migration: `20261004003624`
- migration-history SHA-256:
  `1099e33d3b2e7125e1dee037572e46ae8da390497660e10f70322ec19116949e`
- functions: **128 / 128**
  - SHA-256 `c0039e155f51f93c5a9fcef7c4251258619304e39bb5f7ea3f7fc8fc3d815052`
- columns: **821 / 821**
  - SHA-256 `6d1153db96f7876c9d35268e7ae9ba44650e2103caab3bf9764d8ad115e5b5b0`
- constraints: **346 / 346**
  - SHA-256 `2bc9f84ec91eaa5a637a0ff0ec2fe78bb29953c197c3a98222f4bdfaefb3bd79`
- indexes: **215 / 215**
  - SHA-256 `3d2ad7e49f14c6b795924f99c8426ad7300b7090b3ebfcd7e9db68e0a5968dc7`
- policies: **88 / 88**
  - SHA-256 `248e901bfa38e4709d6f53febe1ef06f22458f7331da77f6d5be6cbfa082d91a`

No positive/runtime evidence was copied:

- builder certification evidence: 0
- factory runs: 0
- deployments: 0
- approvals: 0
- `vl_cert_health` rows: 0

## Deterministic bootstrap — pass 2

A repository-controlled bootstrap file was added:

`vl/migrations/baselines/2026-10-04/bootstrap.sql`

It contains the reviewed schema snapshot plus the explicit DEV-only application-schema reset preamble. It is outside the active migration directory and is marked **NEVER apply to Production**.

The same DEV branch was reset again. Native replay again failed after migration 48. Then **one deterministic `bootstrap.sql` file** was applied, followed by exact migration-history synchronization.

The complete schema/history fingerprint again matched Production exactly.

A DEV-only Supabase branch rebase was then run with no pending Production migration. Branch status recovered to:

- `FUNCTIONS_DEPLOYED`
- preview project status `ACTIVE_HEALTHY`

This proves the canonical baseline recovery path is repeatable.

## Advisors

Security advisor on DEV after baseline:

- `rls_enabled_no_policy`: INFO, 34
- Production has the same INFO count 34.

Performance advisor:

- `unindexed_foreign_keys`: INFO, 2 (same as Production)
- `auth_db_connections_absolute`: INFO, 1 (same as Production)
- `unused_index`: INFO, 99 on empty DEV vs 60 on Production; expected because the data-less DEV branch has no workload/index usage history.

No ERROR-level advisor blocker was observed.

## PR #472 runtime regression

Candidate contracts were installed on DEV only:

1. operational reconciliation contract
2. certification-health freshness contract
3. evidence-bound authoritative certification-health finalizer from PR #472

Fail-closed runtime evidence, repeated after the deterministic second replay:

- no health row => `status=unknown`, `fresh=false`
- finalizer without active builder/policy/evidence =>
  `ok=false`, `status=hold`, `reason=ACTIVE_BUILDER_POLICY_MISMATCH`
- nonexistent reconciliation target => expected `P0002` fail-closed path
- nonexistent approval target => expected `P0002` fail-closed path
- `anon` / `authenticated`: no execute privilege on governed health/reconciliation/writer functions
- `service_role`: execute privilege present
- builder certification evidence remained 0
- factory runs remained 0
- deployments remained 0
- approvals remained 0
- authoritative health rows remained 0
- only a blocked finalizer audit was created on disposable DEV as negative test evidence

No synthetic PASS evidence, approval, deployment, factory run or authoritative health row was manufactured.

## Production non-mutation verification

Final read-only Production fingerprint remained exactly:

- migrations 174
- functions 128
- columns 821
- constraints 346
- indexes 215
- policies 88
- all recorded hashes unchanged

PR #472 candidate functions remained absent from Production:

- `private.finalize_vl_cert_health_from_fresh_certification(...)`: absent
- `public.get_vl_cert_health_effective(integer)`: absent
- `public.vl_reconcile_stale_factory_workflow(...)`: absent

Production `vl.cert_health_finalization_blocked` audit rows created by this recovery: **0**.

## Gate conclusion

- authoritative schema capture: GREEN
- baseline preservation: GREEN
- canonical deterministic bootstrap: GREEN
- exact schema parity: GREEN
- exact migration-history parity: GREEN
- repeated DEV recovery: GREEN
- Supabase branch platform health after recovery/rebase: GREEN
- advisors reviewed: GREEN / INFO-only
- operational reconciliation regression: GREEN
- certification-health fail-closed regression: GREEN
- Production non-mutation: GREEN

Issue #153 is technically **GREEN candidate**, pending repository review/merge of PR #474. Production remains HOLD.
