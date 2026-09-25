# vrs-agent-grant-resolver

Status: **REPOSITORY CANDIDATE / NON-PRODUCTION / NOT DEPLOYED**

## Purpose

Give the LOM VPS a narrowly bounded way to read the exact ACP grant chain needed for one non-Production task without placing a Supabase `service_role` or database credential on the VPS.

Flow:

`VPS handoff -> signed read-only request -> Edge Function -> narrow RPC -> private.agent_capability_grants -> chain rows -> VPS local resolve_grant() validation`

The Edge Function owns the broad server-side credential. The VPS owns only a dedicated HMAC query credential scoped by this endpoint's code to grant-chain reads.

## Security invariants

- read-only operation only;
- exact `grant_ref`, `agent_id`, `project_id`, and `target_environment` binding;
- development/staging only;
- request timestamp bound;
- HMAC request authentication;
- no grant creation, revocation, mutation, audit write, Production access, connector execution, or arbitrary SQL;
- maximum chain depth 16;
- VPS independently reruns the canonical Python `resolve_grant()` logic before using a returned grant;
- stale/revoked/missing/widened chains fail closed.

## Required database RPC

This function expects a future RPC named:

`public.acp_read_agent_grant_chain_nonprod(uuid,text,text,text)`

That RPC is **not introduced by this branch**. It must be generated through the approved Supabase migration workflow, reviewed separately, and must:

1. be read-only;
2. use a pinned/empty `search_path` with fully qualified objects;
3. return only the minimum grant-chain columns required by `grant_resolution.py`;
4. reject Production target environments;
5. bind the leaf grant to exact agent/project/environment;
6. cap traversal depth at 16 and reject cycles;
7. revoke EXECUTE from `public`, `anon`, and `authenticated`;
8. grant EXECUTE only to the server-side role used by this Edge Function;
9. provide no direct SELECT/DML grants on `private.agent_capability_grants`.

No database migration is included here because the migration must be generated and verified through the Supabase CLI/database workflow rather than invented manually.

## Deployment gate

Do not deploy this Edge Function or put its query secret on the VPS until the RPC exists, database advisors are clean for the change, and an end-to-end non-Production test proves:

`signed query -> RPC -> grant rows -> local chain resolution -> ACP/VPS execution -> evidence`.
