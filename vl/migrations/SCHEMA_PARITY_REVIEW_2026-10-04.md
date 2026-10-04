# VL Schema Parity Review — 2026-10-04

Status: authoritative read-only capture reviewed. No Production database mutation is authorized by this report.

## Capture provenance

- Workflow: `VL Schema Capture Evidence`
- Run: `37208650759` / run #4
- Branch: `fix/vl-migration-reproducibility-refresh-20261004`
- HEAD: `3d99fbfcce9628d93cf2250d1490f02f4ef46241`
- Result: SUCCESS
- Artifact: `vl-schema-capture-evidence` (artifact id `11305628752`)
- GitHub artifact digest: `sha256:1949d6ff4d58d65ce7c2501811ec04f01fba9174bf6e4cc37740facabfd6f67f`
- Artifact retention: 1 day
- `remote_schema.sql` SHA-256: `50d426da6ad13641d5ef3d44b0a3fa84ea61828e4c549d4fef6faa5ef812afb5`
- `SHA256SUMS.txt` SHA-256: `1f6b3c60298f2a4babe6320e15cda11af4e2bb34d087d2f1f047d025186a9d38`
- Fetched migration files: **174**
- All fetched migration checksums: **PASS**
- Schema dump contains INSERT statements: **0**
- Schema dump contains COPY statements: **0**
- Credential-pattern scan: **PASS** (artifact upload was allowed)

## Current Production metadata

Read-only metadata captured on the same recovery cycle:

- migration history: **174**
- latest migration: `20261004003624`
- functions: **128**
- columns: **821**
- constraints: **346**
- indexes: **215**
- policies: **88**

## Repository vs remote history

The repository `vl/migrations` currently contains **37 SQL files**.

The authoritative remote history contains **174 migrations**.

- exact filename/version matches: **0**
- remote migrations with a matching logical filename stem in the repository: **27**
- remote migrations without a matching logical stem in the repository: **147**

This means the repository migration directory is not a faithful copy of the authoritative remote migration history and must not be treated as a complete replay source.

## Confirmed schema drift

`public.vl_cert_health` is present in the authoritative schema dump:

- table exists;
- primary key exists;
- RLS is enabled;
- read policy exists;
- service-role and read grants exist.

However, **zero of the 174 fetched migration files contain `vl_cert_health`**.

Therefore `public.vl_cert_health` is authoritative evidence of schema state that is not represented by migration history. This is a genuine schema-drift/provenance gap, not a DEV replay bug.

## Additional legacy ordering/provenance gaps

The fetched history also confirms earlier replay findings: several objects are referenced/hardened before their reproducible creation is available in the historical chain, or have no creation statement in the chain.

Examples include:

- `private.production_adapter_registry` — no CREATE TABLE in fetched migration history;
- `private.builder_release_gate_profiles` — no CREATE TABLE in fetched migration history;
- `private.release_validation_jobs` — no CREATE TABLE in fetched migration history;
- `public.vl_cert_health` — no CREATE TABLE in fetched migration history;
- production-promotion RPCs and other control-plane objects are created or replaced only in later migrations after earlier migrations already depend on them.

The legacy chain therefore cannot safely be made reproducible merely by renaming local files or replaying the 174 fetched migrations from an empty database.

## Recovery decision

Do **not** mutate Production migration history merely to make repository history appear aligned.

Do **not** edit historical migrations in place.

Do **not** seed synthetic certification PASS evidence, approvals, deployments, health timestamps, or other positive lifecycle state.

The canonical recovery path is:

1. Preserve the authoritative schema snapshot and its digest as baseline evidence.
2. Establish a **schema-only canonical baseline** for fresh environments, outside the legacy active migration chain.
3. On a new data-less DEV branch, apply the canonical baseline through a deterministic bootstrap path.
4. Verify exact schema/fingerprint parity with Production before any migration-history tracking repair.
5. Only after parity is proven, synchronize DEV migration tracking for the 174 legacy versions; tracking repair must never claim schema was created when it was not.
6. Apply only migrations newer than the accepted baseline through the normal forward-only path.
7. Verify that a second fresh DEV bootstrap succeeds without manual DDL scaffolding or synthetic evidence.
8. Run security/performance advisors.
9. Re-run operational reconciliation and certification-health regression.
10. Verify Production read-only for zero unintended mutation.

## Gate state

- Operator schema capture: **GREEN**
- Artifact integrity: **GREEN**
- Legacy migration chain as a standalone fresh bootstrap: **RED / historical limitation confirmed**
- Canonical baseline: **GREEN**
- Exact schema parity on data-less DEV: **GREEN**
- Exact migration-history parity on DEV after schema parity: **GREEN**
- Repeat deterministic DEV replay: **GREEN**
- PR #472 runtime proof: **GREEN candidate on DEV**
- Production non-mutation verification: **GREEN**
- Production activation: **HOLD**



## Baseline preservation

The reviewed capture was promoted to repository evidence by workflow run `37209604260`.

- promotion commit: `3943b787ad3a71678a4af582f695516bd9dd97a9`
- recovery branch only: `fix/vl-migration-reproducibility-refresh-20261004`
- preserved files:
  - `vl/migrations/baselines/2026-10-04/remote_schema.sql.gz`
  - `vl/migrations/baselines/2026-10-04/fetched_migrations.tar.gz`
  - `vl/migrations/baselines/2026-10-04/SHA256SUMS.txt`
  - `vl/migrations/baselines/2026-10-04/PROVENANCE.json`
- no Production database mutation occurred.


## Validation closure

The recovery path above was executed twice on an isolated data-less DEV branch. The repository-controlled baseline reproduced the exact Production schema and migration-history fingerprints, Supabase branch health recovered to `FUNCTIONS_DEPLOYED / ACTIVE_HEALTHY`, runtime fail-closed regressions passed, and the temporary DEV branch was deleted. See `DEV_REPLAY_EVIDENCE_2026-10-04.md`.

The legacy migration chain remains historically incomplete and is intentionally not rewritten. The accepted recovery mechanism is the canonical baseline + forward-only migrations after the baseline. Production activation remains a separate human gate.
