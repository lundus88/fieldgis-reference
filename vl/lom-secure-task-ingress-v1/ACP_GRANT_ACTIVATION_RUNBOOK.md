# LOM Direct VPS — ACP Grant Activation Runbook

Status: **PREPARED / NON-PRODUCTION / HUMAN-GATED / NOT APPLIED**

## Verified live baseline

Read-only inspection of the active `vrs-core` Supabase project confirms:

- `private.agent_capability_grants` exists;
- `private.agent_control_audit_events` exists;
- `public.acp_delegate_agent_grant_nonprod(...)` exists;
- `public.acp_revoke_agent_grant(...)` exists;
- `public.acp_read_agent_grant_chain_nonprod(...)` does **not** yet exist;
- there are currently **zero active non-Production grants**;
- there is currently **no active grant for `lom-vps-runner`**;
- the previous staging parent grant is expired;
- the previous staging child canary grant is revoked;
- `vrs-agent-control-oidc` is deployed and active.

These facts mean direct LOM -> VPS execution must remain HOLD until a fresh bounded authority chain and read-only resolver exist.

## Canonical target scope

The direct VPS path should use the existing logical project:

- project slug: `fieldgis-reference`
- target environment: `staging`
- environment status requirement: `ready`

The database/project UUID must be resolved from the authoritative project store at activation time. Do not hardcode a generated UUID into reusable policy code.

## Required authority chain

### Parent grant — HUMAN GATE

A fresh parent grant is required because the old parent has expired.

Minimum parent authority:

- principal type: `system`
- role: dedicated LOM/VPS staging parent
- capability: `factory.plan` only
- project: resolved `fieldgis-reference`
- target environment: `staging`
- timeout budget: at most 60 seconds
- max retries: 0
- max cost: 0
- short validity window, default 24 hours
- no Production capability
- no connector capability
- no protected-main merge authority

Creating a new parent/root grant is **HUMAN_ONLY**. Existing runtime delegation APIs must not be extended to mint root authority.

### Child grant — existing governed path

After a valid parent exists, use the existing OIDC admin workflow to delegate:

- agent_id: `lom-vps-runner`
- capability: `factory.plan`
- same project/environment scope as parent
- budget no wider than parent
- validity no wider than parent

The child grant must be persisted in the authoritative ACP store and independently resolved before execution.

## Read-only grant resolver RPC

A separately reviewed Supabase migration must introduce:

`public.acp_read_agent_grant_chain_nonprod(uuid,text,text,text)`

Required properties:

1. read-only;
2. reject target environments other than `development` or `staging`;
3. bind the leaf grant to exact `grant_id`, `agent_id`, `project_id`, and target environment;
4. traverse only `private.agent_capability_grants`;
5. maximum depth 16;
6. reject missing ancestors and cycles;
7. return only fields required by canonical `grant_resolution.py`;
8. no INSERT/UPDATE/DELETE;
9. no generic SQL or arbitrary table selection;
10. revoke EXECUTE from `public`, `anon`, and `authenticated`;
11. grant only the minimum server-side role required by the dedicated Edge Function;
12. do not grant direct SELECT/DML on the private ACP tables.

The migration must be generated through the approved Supabase migration workflow, reviewed, applied only after human approval, and followed by security/performance advisors.

## Edge resolver

Only after the RPC exists:

- deploy `vrs-agent-grant-resolver`;
- use the server-side Supabase credential only inside the Edge Function;
- never place `SUPABASE_SERVICE_ROLE_KEY` on the VPS;
- give VPS only a dedicated HMAC query secret;
- bind every request to timestamp, nonce, agent, project, environment, and grant ref;
- fail closed on stale, missing, revoked, widened, or malformed grant chains.

## VPS handoff

The VPS must store only bounded local secrets with mode `0600`:

- Secure Task Ingress HMAC key;
- grant-query HMAC key.

It must not receive:

- Supabase service-role key;
- GitHub token;
- Production credentials;
- Docker socket;
- root/sudo authority for `lom-runner`.

## End-to-end activation proof

Activation requires all of the following in one controlled non-Production window:

1. fresh parent grant exists;
2. bounded `lom-vps-runner` child grant exists;
3. read-only resolver RPC exists;
4. resolver Edge Function authenticates the VPS query;
5. local canonical `resolve_grant()` accepts the returned chain;
6. Secure Task Ingress accepts a correctly signed task;
7. ACP authorizes `factory.plan` only;
8. VPS worker prepares the bounded result;
9. execution/evidence journals verify;
10. identical replay is idempotent;
11. changed replay is rejected;
12. Production/connector attempts are rejected;
13. worker and heartbeat remain healthy after restart.

Only after all checks PASS may the office workstation be classified as an optional emergency/admin fallback rather than a normal operational dependency.

## Stop conditions

Immediate HOLD if any of the following occurs:

- public ingress exposure;
- missing or stale live VPS canary;
- missing/expired/revoked grant;
- grant capability or scope widening;
- resolver returns an unverified chain;
- service-role credential appears on VPS;
- Production capability appears in any grant;
- connector capability is introduced;
- audit/evidence chain fails;
- worker/heartbeat regression occurs.
