# LOM Direct VPS — ACP Grant Activation Runbook

Status: **NON-PRODUCTION / VPS LIVE-VERIFIED / AUTHORITY ACTIVE / RESOLVER HMAC PROOF VERIFIED**

## Current verified live state — 2026-10-01

The canonical VPS activation has advanced beyond the historical preparation baseline:

- `private.agent_capability_grants` and ACP audit storage are live;
- `public.acp_delegate_agent_grant_nonprod(...)` and revocation RPCs are live;
- `public.acp_read_agent_grant_chain_nonprod(...)` is live;
- the short-lived `lom-vps-staging-parent` grant is active;
- the bounded `lom-vps-runner` child grant is active for `factory.plan` in `staging`;
- `vrs-agent-control-oidc` is ACTIVE;
- `vrs-agent-grant-resolver` is ACTIVE;
- canonical node `v103067` has real 13/13 live canary PASS;
- Secure Task Ingress is READY and loopback-only;
- worker, heartbeat timer and ingress are verified through reboot recovery;
- VPS operational probe reported HEALTHY;
- office workstations remain excluded from runtime.

The HMAC-authenticated resolver path from `v103067` through the Edge resolver and back into local canonical grant resolution is now live-verified.

The active authority is short-lived and expires on 2026-10-01 at approximately 22:13:48 MYT unless renewed through the same governed human-approved path.

## Canonical target scope

- project slug: `fieldgis-reference`;
- project ID: `432a4a98-1199-4326-a37c-41e2477a1d08`;
- target environment: `staging`;
- agent: `lom-vps-runner`;
- capability: `factory.plan` only;
- canonical runtime node: `v103067`.

## Authority chain

Current chain:

`lom-vps-runner -> lom-vps-staging-parent`

The child must never exceed the parent capability, scope, budget or validity. Root/parent renewal remains HUMAN_ONLY.

## Read-only grant resolver

The existing deployed resolver is:

`vrs-agent-grant-resolver`

The VPS must never receive `SUPABASE_SERVICE_ROLE_KEY`. The Edge Function owns the server-side credential and exposes only the bounded read-only HMAC-authenticated grant query.

Every request binds:

- timestamp;
- nonce;
- agent;
- project;
- environment;
- grant ref.

Stale, missing, revoked, widened, malformed or Production-scoped chains fail closed.

## VPS HMAC handoff

Use the existing `grant_resolver_client.py`; do not create a second client or transport.

The VPS stores only the dedicated grant-query HMAC key with mode `0600`.

It must not receive:

- Supabase service-role key;
- GitHub token;
- Production credentials;
- Docker socket;
- root/sudo authority for `lom-runner`.

## Resolver proof

Resolver-specific completion is verified with live evidence:

1. positive signed query succeeded for the current child grant;
2. returned chain was accepted by canonical `resolve_grant()`;
3. bad signature was rejected with HTTP 401;
4. stale timestamp was rejected with HTTP 401;
5. wrong agent/project/environment were rejected with HTTP 409;
6. Production target was rejected with HTTP 400;
7. Edge log audit for the proof window found no secret-name, HMAC-signature, or signature-header exposure.

This verifies the bounded read-only transport only. It does not widen capability, grant lifetime, environment scope, connector access or Production authority.

## Existing live VPS proof

The runtime activation evidence already establishes:

- 13/13 live canary PASS;
- dedicated unprivileged `lom-runner`;
- Production/connector denials;
- idempotent identical replay and changed replay rejection;
- evidence journal integrity;
- heartbeat availability;
- Secure Task Ingress READY and loopback-only;
- reboot recovery;
- operational probe HEALTHY.

This proof remains freshness-bound. A repository SHA mismatch, stale canary, public ingress exposure, failed service recovery or weakened authority boundary returns the node to HOLD.

## Stop conditions

Immediate HOLD if:

- public ingress exposure;
- stale or repository-mismatched live canary;
- missing/expired/revoked grant;
- grant capability or scope widening;
- resolver returns an unverified chain;
- service-role credential appears on VPS;
- Production or connector capability appears;
- audit/evidence chain fails;
- worker/heartbeat regression occurs.

Production authority remains HUMAN_ONLY.
