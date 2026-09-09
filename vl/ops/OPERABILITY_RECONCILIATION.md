# VL Operability Reconciliation

Status: proposed fail-closed repair contract. This branch does not deploy or mutate the live control plane.

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

## Files

- `reconciliation_contract.sql`: candidate database contract for governed orphan reconciliation and explicit stale-approval expiry.
- `health_freshness_contract.sql`: read-only effective-health calculation that converts old signals to `stale`.
- `check_operational_contract.py`: CI governance checks preventing positive lifecycle/deployment mutations from entering this patch.

## Required rollout gates

Before runtime activation:

1. Create an isolated Supabase development branch using the normal project tooling and cost approval process.
2. Materialize the SQL as a proper Supabase migration using the project migration workflow; do not ad-hoc apply this candidate SQL to live `vrs-core`.
3. Run database tests covering the two historical state pairs, idempotency, under-age rejection, production-deployment rejection and stale approval expiry.
4. Run Supabase security and performance advisors.
5. Add an OIDC-authenticated operational reconciler that passes verified GitHub identity to the service-role-only RPC wrappers.
6. Run a dry-run inventory and require zero production-environment candidates.
7. Reconcile only the explicitly reviewed historical IDs.
8. Re-query the live control plane read-only and confirm no affected row gained production authority.

## Non-goals

- No production approval.
- No production promotion.
- No production deployment.
- No synthetic PASS evidence.
- No weakening of certified-deployment or immutable provenance requirements.
