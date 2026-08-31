# VL Agent Control Plane — Production Rollout Runbook

Status: **PLANNING ONLY — NOT APPROVED / NOT APPLIED**

This runbook defines the only supported sequence for introducing Agent Control Plane (ACP) persistence and the narrow live write boundary into the Supabase production project. It is deliberately fail-closed and does not itself authorize any database migration, Edge Function deployment, admin workflow activation, or root/parent grant bootstrap.

## Non-negotiable rules

1. Production promotion remains behind explicit human approval.
2. Never use a manual workflow run as evidence for the separate VL Factory Runner natural-scheduler incident.
3. Apply ACP changes one phase at a time. Do not batch database, Edge Function, workflow, and grant bootstrap into one uncontrolled change.
4. Stop immediately if observed production state differs from the expected preflight state.
5. Preserve audit evidence. Once any ACP audit event exists, rollback means disabling the write path while retaining evidence; do not drop the audit store.
6. `service_role` must never receive direct INSERT/UPDATE/DELETE/TRUNCATE rights on ACP private tables.
7. The live boundary must never issue a root grant, delegate `production.approve` / `production.promote`, or accept a production target environment.
8. No ACP stage may weaken existing release, certification, OIDC, sandbox, or human approval controls.

## Authoritative repository inputs

The rollout must be pinned to one reviewed `main` commit and the exact repository files at that commit:

- `vl/migrations/20260831_agent_control_plane_store.sql`
- `vl/migrations/20260901_agent_control_plane_live_boundary.sql`
- `vl/functions/vrs-agent-control-oidc/index.ts`
- `vl/functions/vrs-agent-control-oidc/README.md`
- `vl/agent-control-plane/check_persistence_contract.py`
- `vl/agent-control-plane/check_live_write_boundary.py`

Before any production write, record:

- `main` commit SHA;
- SHA-256 of both migration files and Edge Function source;
- latest successful `VL Governance CI` run for that SHA;
- latest successful `VL Agent Control Plane CI` run for that SHA;
- Supabase project ref;
- operator/founder approval evidence;
- timestamp of the production change window.

If any source SHA changes after approval, approval is stale and the rollout must restart from preflight.

---

# Phase 0 — Founder approval checkpoint

**Required state:** repository-only ACP implementation; no ACP production tables, RPCs, Edge Function, admin workflow or root/parent grant active.

Required explicit approvals must be separated:

- Approval A — apply ACP store migration.
- Approval B — apply ACP live-boundary migration.
- Approval C — deploy `vrs-agent-control-oidc` with custom OIDC verification.
- Approval D — introduce/enable the dedicated ACP admin workflow.
- Approval E — bootstrap a root/parent grant.

A later approval does not imply an earlier or broader one. Production promotion approval is unrelated and remains governed by the existing release gate.

**STOP:** Do not continue without explicit approval for the next production-changing phase.

---

# Phase 1 — Read-only production preflight

Run read-only checks only.

Expected baseline before first ACP migration:

- schema `private` exists;
- extension `pgcrypto` exists under `extensions`;
- `private.agent_capability_grants` does not exist;
- `private.agent_control_audit_events` does not exist;
- ACP boundary RPCs do not exist;
- no `vrs-agent-control-oidc` production deployment is claimed;
- existing VL release/promotion gates remain unchanged.

Capture the result of read-only catalog queries for:

- `to_regclass` / `to_regprocedure` of every ACP object;
- `pg_extension` location for `pgcrypto`;
- current `service_role` privileges on schema `private`;
- current functions with names beginning `acp_` in `public` or `private`;
- current table row counts if any ACP table unexpectedly exists.

**STOP CONDITIONS:**

- any ACP object already exists unexpectedly;
- an existing object has a different owner/signature than the reviewed migration expects;
- `pgcrypto` is not available under `extensions`;
- another migration or deployment is concurrently modifying ACP objects;
- latest required CI evidence is not successful.

Do not “repair around” unexpected state. Diagnose first.

---

# Phase 2 — Apply ACP store migration only

**Input:** `20260831_agent_control_plane_store.sql` from the approved `main` SHA.

Use the platform migration mechanism intended for DDL. Do not substitute an ad-hoc sequence of hand-edited SQL statements.

Expected objects include:

- `private.agent_capability_grants`;
- `private.agent_control_audit_events`;
- delegation validation trigger/function;
- audit-chain validation trigger/function;
- update/delete/truncate blocking trigger/function.

No grant rows or audit rows should be created by this migration.

## Phase 2 verification

Verify immediately:

- both ACP tables exist;
- both tables contain zero rows;
- agent grants cannot contain `production.approve` or `production.promote`;
- DB delegation validator exists;
- audit chain validator exists;
- UPDATE, DELETE and TRUNCATE blockers exist on audit table;
- `service_role`, `anon`, `authenticated`, and `public` have no direct ACP table DML;
- internal validation functions are not executable by exposed roles/service role;
- no public ACP write RPC exists yet.

Record catalog evidence and migration identifier.

**STOP:** Any verification failure blocks Phase 3. Do not deploy the Edge Function.

## Phase 2 rollback

If verification fails before any ACP data exists:

1. stop further rollout;
2. capture failure evidence;
3. prefer a reviewed corrective migration over ad-hoc mutation;
4. only if explicit rollback approval is given and both tables are proven empty may the newly created ACP objects be removed.

If any audit row exists, do **not** drop the audit store. Move to fail-closed containment instead.

---

# Phase 3 — Apply narrow live-boundary migration only

**Input:** `20260901_agent_control_plane_live_boundary.sql` from the approved `main` SHA.

Expected public service-role-executable RPC surface must be exactly:

- `public.acp_delegate_agent_grant_nonprod(...)`
- `public.acp_revoke_agent_grant(...)`

Expected properties:

- both are `SECURITY DEFINER` with fixed `search_path`;
- no root-grant issuance RPC exists;
- no generic audit-write RPC exists;
- only service role receives EXECUTE on the two public RPCs;
- actor evidence is revalidated at the DB boundary;
- exact replay is idempotent;
- changed-input replay fails closed;
- reuse of one `action_id` for another operation fails closed;
- grant/audit mutations are atomic.

## Phase 3 verification

Use catalog/privilege checks to prove:

- exactly two `public.acp_*` functions are executable by `service_role` for this boundary;
- `anon` and `authenticated` cannot execute them;
- `service_role` still cannot directly mutate either ACP table;
- no `public.acp_create_root_grant`, `public.acp_issue_root_grant`, or generic public audit writer exists;
- tables remain empty unless a separately approved test fixture has been inserted;
- existing release/promotion functions and policies were not changed.

**STOP:** Any privilege expansion or unexpected function blocks Edge Function deployment.

## Phase 3 fail-closed rollback

Preferred containment is to revoke EXECUTE on both public boundary RPCs from `service_role`, leaving ACP tables and audit evidence intact.

Do not drop audit evidence to “clean up” a failed rollout.

---

# Phase 4 — Edge Function deployment checkpoint

This phase requires separate explicit approval.

Candidate: `vl/functions/vrs-agent-control-oidc/index.ts`.

Deployment requirements:

- deploy exact reviewed source SHA;
- `verify_jwt=false` is intentional only because the function performs custom GitHub OIDC signature/claim verification itself;
- audience must be `vrs-agent-control-plane`;
- repository must be `lundus88/fieldgis-reference`;
- ref must be `refs/heads/main`;
- allowed workflow must be exactly `.github/workflows/vl-agent-control-plane-admin.yml@refs/heads/main`;
- service-role secret remains server-side and is never returned or logged;
- only the two narrow RPCs are called;
- no direct table access is introduced.

At this phase the dedicated admin workflow should still be absent. Therefore a correctly configured deployment is expected to remain operationally fail-closed to GitHub workflow calls.

## Phase 4 verification

Capture:

- Edge Function version/status;
- deployed source digest;
- `verify_jwt` configuration;
- a negative unauthenticated request proving 401;
- a negative token with wrong audience/workflow/ref proving 401, where safe test infrastructure exists;
- absence of any ACP table mutation from negative tests.

**STOP:** Do not create/enable the admin workflow until negative auth behavior is proven.

## Phase 4 rollback

Disable/remove the Edge Function caller path or restore the previously known-safe function state. Keep DB boundary EXECUTE revoked if there is uncertainty. Preserve all audit evidence.

---

# Phase 5 — Root/parent grant bootstrap checkpoint

Runtime root-grant issuance is intentionally impossible through the live boundary.

A root/parent grant must be introduced only by a separately reviewed, founder-approved bootstrap mechanism. The bootstrap must:

- create only the minimum capabilities needed for the first staging canary;
- bind `target_environment` to `staging`;
- use a narrow project/factory scope;
- set bounded `valid_from` / `valid_until`;
- set conservative time/retry/cost budgets;
- never include `production.approve` or `production.promote`;
- record who approved and created it;
- be independently auditable.

Do not create an unrestricted “superuser agent” root grant.

**STOP:** no parent grant, no live delegation test.

---

# Phase 6 — Dedicated admin workflow checkpoint

Create `.github/workflows/vl-agent-control-plane-admin.yml` only in a separate reviewed PR.

Minimum requirements:

- `permissions: contents: read` and `id-token: write`; no broader GitHub token permissions unless separately justified;
- exact OIDC audience `vrs-agent-control-plane`;
- runs only from `main` under the intended controlled trigger;
- no stored Supabase service-role key in GitHub Actions;
- sends only bounded operation payloads to the Edge Function;
- does not expose root grant creation;
- does not expose production approval/promotion;
- does not auto-run as a broad scheduler until staging evidence exists;
- captures run ID/SHA/action ID as evidence.

Merge of this workflow is not evidence of successful ACP enforcement.

---

# Phase 7 — Staging-scope end-to-end canary

Only after Phases 2–6 are explicitly approved and verified.

Use a disposable/staging-scoped parent grant and deterministic test action IDs.

Required positive case:

1. GitHub OIDC token is issued to the exact admin workflow.
2. Edge verifies signature and claims.
3. `delegate_grant` creates one bounded child agent grant with `target_environment=staging`.
4. One immutable audit event is appended in the same transaction.
5. Exact replay returns the same grant ID without creating a second grant or second mutation.
6. `revoke_grant` revokes the child and atomically appends evidence.

Required negative cases:

- unknown operation → blocked;
- wrong audience → 401;
- wrong workflow/ref/repository → 401;
- malformed payload → 400;
- production target → blocked;
- `production.approve` / `production.promote` capability → blocked;
- child capability wider than parent → blocked;
- scope escape → blocked;
- budget expansion → blocked;
- validity beyond parent → blocked;
- changed-input replay with same action ID → blocked;
- same action ID reused for another operation → blocked;
- direct service-role DML on ACP private tables remains denied.

For every blocked case, prove no unintended grant/audit mutation occurred except audit evidence intentionally generated by an approved boundary behavior.

**PASS requires machine-readable evidence.** Do not infer PASS from HTTP status alone.

---

# Phase 8 — Operational observation

After the staging canary passes:

- keep capabilities and scope narrow;
- observe errors, audit-chain integrity, replay behavior, and grant expiry/revocation;
- do not broaden to production target environment in ACP V1;
- do not connect broad multi-agent orchestration until selected non-production transitions have end-to-end enforcement evidence.

Production release approval/promotion remains outside ACP autonomous authority.

---

# Emergency containment

If any ACP behavior is suspicious:

1. stop/disable the ACP admin caller workflow;
2. revoke EXECUTE on the two public ACP boundary RPCs from `service_role`;
3. disable the Edge Function if necessary;
4. revoke affected agent grants through an approved path if the boundary is trustworthy; otherwise use a founder-approved containment migration;
5. preserve the append-only audit table;
6. capture GitHub run ID, commit SHA, Edge logs, DB logs, affected grant IDs, action IDs, and audit digests;
7. investigate before re-enabling.

Emergency containment must not bypass the separate human production release gate.

---

# Rollout completion criteria

ACP live-write rollout is **not complete** until all of the following have evidence:

- store migration applied and verified;
- live-boundary migration applied and verified;
- Edge Function deployed with exact custom OIDC configuration;
- root/parent staging grant separately approved and bounded;
- dedicated admin workflow reviewed and merged;
- staging positive canary PASS;
- all required negative/adversarial canaries PASS;
- exact replay proven idempotent;
- changed replay proven fail-closed;
- append-only audit integrity verified;
- direct table DML remains unavailable to service role;
- existing human production approval path remains unchanged.

Until then, report ACP as **repository-ready / rollout-in-progress**, never as production-live.
