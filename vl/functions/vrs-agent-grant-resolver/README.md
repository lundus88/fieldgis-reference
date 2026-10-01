# vrs-agent-grant-resolver

Status: **DEPLOYED / NON-PRODUCTION / VPS LIVE-VERIFIED / HMAC END-TO-END VERIFIED**

Live state verified on 2026-10-01:

- Edge Function `vrs-agent-grant-resolver` is deployed and `ACTIVE`;
- the required read-only grant-chain RPC is live;
- the bounded `lom-vps-runner -> lom-vps-staging-parent` chain is active for `factory.plan` in `staging`;
- canonical VPS node `v103067` is live-verified non-Production with 13/13 canary PASS;
- Secure Task Ingress is READY and loopback-only, reboot recovery is verified, and the operational probe is HEALTHY;
- the signed HMAC resolver path from canonical VPS `v103067` is live-verified end-to-end.

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

The required RPC is live:

`public.acp_read_agent_grant_chain_nonprod(uuid,text,text,text)`

Verified behavior:

1. bounded read-only grant-chain resolution;
2. non-Production scope binding;
3. exact leaf binding by grant, agent, project and environment;
4. maximum chain depth 16;
5. no direct private-table credential is placed on the VPS;
6. the active child -> parent staging chain resolves successfully.

## Current activation boundary

The VPS runtime and resolver transport are live-verified non-Production.

Verified flow:

`v103067 -> signed HMAC query -> Edge resolver -> read-only RPC -> returned grant chain -> local canonical resolve_grant()`

Live evidence on 2026-10-01 established:

- dedicated `LOM_VPS_GRANT_QUERY_SECRET` provisioned through the approved Edge Function secret path;
- matching VPS-side secret stored under `lom-runner` with mode `0600`;
- positive signed query accepted and resolved to `factory.plan` in `staging`;
- wrong signature rejected with HTTP 401;
- stale timestamp rejected with HTTP 401;
- wrong agent/project/environment rejected with HTTP 409;
- Production target rejected with HTTP 400;
- Edge log audit for the proof window found zero occurrences of the secret name, HMAC signature material, or `x-lom-signature` header;
- no `SUPABASE_SERVICE_ROLE_KEY` is placed on the VPS.

The proof remains freshness- and authority-bound. Expired/revoked grants, credential rotation, repository/runtime drift, widened scope, Production targeting, public ingress exposure, or resolver verification failure must return the relevant path to HOLD.

Production authority remains `HUMAN_ONLY`.
