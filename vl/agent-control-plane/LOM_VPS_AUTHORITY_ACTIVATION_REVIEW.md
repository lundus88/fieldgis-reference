# LOM VPS Authority Activation Review

Status: **REVIEW PACK ONLY — NO LIVE CHANGE**

This pack prepares the two database-side gates required before PR #399 can become operational.

## Candidate A — read-only grant resolver RPC

File:

`sql-candidates/acp_read_agent_grant_chain_nonprod.sql`

Review objective:

- prove it can read only one bounded non-Production grant chain;
- prove it cannot mutate ACP state;
- prove it cannot expose Production authority;
- prove EXECUTE is restricted to the server-side resolver role;
- prove no direct private-table access is granted to VPS or API clients.

The privileged reader is now a SECURITY DEFINER function in the private schema. The exposed public RPC is SECURITY INVOKER only and delegates to the private implementation. Both functions use an empty search path, explicit EXECUTE revocation, and service-role-only execution. The public wrapper contains no direct grant-table access or privileged SQL.

## Verified pre-apply baseline — 2026-09-25

Read-only live checks on `vrs-core` confirmed:

- PostgreSQL 17.6;
- `service_role` has USAGE on schema `private`;
- `service_role` has no direct SELECT on `private.agent_capability_grants`;
- the read-only resolver RPC is not yet live;
- active non-production grants: 0;
- active `lom-vps-runner` grants: 0.

Supabase advisors were also captured before any DDL. Security findings are existing INFO-level private-table RLS-with-no-policy notices; performance findings are existing INFO-level unindexed/unused-index notices. None was created by this candidate because no DDL has been applied. Re-run both advisor classes immediately after any approved migration application.

## Candidate B — short-lived staging parent grant renewal

File:

`sql-candidates/acp_lom_vps_parent_grant_renewal.sql`

This is a one-time human-approved migration action, not a runtime RPC.

Target:

- logical project: `fieldgis-reference`
- environment: `staging`
- capability: `factory.plan`
- timeout: 60 seconds
- retries: 0
- max cost: 0
- validity: 24 hours
- root/system parent only
- no Production, connector, release, payment or merge capability.

It refuses to create a duplicate active parent for the same scope and records immutable ACP audit evidence in the same transaction.

## Migration workflow after approval

Do **not** copy these files into `vl/migrations` with an invented timestamp.

After explicit human approval:

1. use the current Supabase CLI migration command to generate an official migration file for Candidate A;
2. place the reviewed SQL into that generated migration;
3. verify migration list/diff;
4. apply to the approved non-Production activation target;
5. run Supabase security and performance advisors;
6. test Candidate A with negative cases before proceeding;
7. repeat the official migration-generation flow for Candidate B;
8. after the parent exists, use the existing GitHub OIDC ACP admin workflow to delegate the bounded `lom-vps-runner` child grant;
9. verify the authoritative grant chain;
10. only then consider Edge resolver deployment and VPS secret handoff.

## Human gates

The following remain HUMAN_ONLY:

- approving Candidate A for migration/application;
- approving Candidate B parent/root grant creation;
- Production scope or capability expansion;
- secret distribution to VPS;
- protected-main merge;
- live VPS activation.

PR #399 remains separate: it contains the resolver client/Edge candidate. This pack only supplies the authority-layer review material required to unblock it safely.
