# LOM VPS Authority Activation Review

Status: **LIVE NON-PRODUCTION AUTHORITY ACTIVE / VPS LIVE-VERIFIED / RESOLVER HMAC PROOF VERIFIED**

## Current verified live state — 2026-10-01

The original review pack has advanced through the governed activation path:

- `public.acp_read_agent_grant_chain_nonprod(uuid,text,text,text)` is live;
- short-lived `lom-vps-staging-parent` authority is active;
- delegated `lom-vps-runner` authority is active with `factory.plan` only;
- delegation was issued through the existing GitHub OIDC ACP admin workflow and immutable audit evidence was recorded;
- `vrs-agent-grant-resolver` is deployed and ACTIVE as a non-Production Edge Function;
- canonical VPS node `v103067` has 13/13 live canary PASS;
- Secure Task Ingress is READY and loopback-only;
- worker, heartbeat and ingress survived the verified reboot/recovery flow;
- the read-only VPS operational probe reported HEALTHY;
- Production remains HUMAN_ONLY and office workstations remain excluded from runtime.

The signed HMAC query path between `v103067` and `vrs-agent-grant-resolver` is now live-verified end-to-end.

The active parent and child grants are short-lived and expire on 2026-10-01 at approximately 22:13:48 MYT unless renewed through the governed human-approved path.

## Candidate A — read-only grant resolver RPC

File:

`sql-candidates/acp_read_agent_grant_chain_nonprod.sql`

The approved live RPC is bounded to non-Production grant-chain reads. The public wrapper is SECURITY INVOKER and delegates to the reviewed private implementation. Execution remains restricted to the server-side resolver role; the VPS does not receive direct private-table access.

## Historical pre-apply baseline — 2026-09-25

Before activation:

- the read-only resolver RPC was not yet live;
- active non-Production grants were 0;
- active `lom-vps-runner` grants were 0.

This section is historical evidence only and must not be interpreted as current state.

## Candidate B — short-lived staging parent grant

Applied target:

- logical project: `fieldgis-reference`;
- environment: `staging`;
- capability: `factory.plan`;
- timeout: 60 seconds;
- retries: 0;
- max cost: 0;
- validity: short-lived;
- no Production, connector, release, payment or merge capability.

The bounded child grant was then delegated through the existing GitHub OIDC ACP admin workflow.

## Applied governed workflow

1. approved read-only RPC applied and verified;
2. security/performance advisors checked;
3. human-approved short-lived parent grant applied;
4. bounded `lom-vps-runner` child delegated through GitHub OIDC;
5. authoritative child -> parent chain verified;
6. existing Edge resolver deployed;
7. real VPS activation gate completed with 13/13 canary PASS;
8. Secure Task Ingress, reboot recovery and operational probe verified.

## Resolver-specific verification complete

No new runtime module was created. The existing resolver client and Edge Function were reused.

Verified on 2026-10-01:

1. the dedicated HMAC query secret was provisioned through the approved secrets path;
2. the matching VPS-side key is owned by `lom-runner` with mode `0600`;
3. positive signed resolution succeeded for the active `factory.plan` staging grant;
4. fail-closed negative cases succeeded for bad signature, stale timestamp, wrong agent/project/environment and Production target;
5. Edge logs for the proof window contained no secret name, HMAC signature material or signature header;
6. Production remains HUMAN_ONLY.

The proof is not an authority expansion and does not authorize Production, connectors, payment, merge, release or legal/customer commitments.

## Human gates

The following remain HUMAN_ONLY:

- parent/root grant renewal or replacement;
- Production scope or capability expansion;
- secret distribution to VPS;
- protected-main merge;
- future live VPS re-activation after stale/relevant changes;
- consequential recovery.

No Production deployment or authority widening is implied by this state.
