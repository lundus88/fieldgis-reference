# vrs-agent-control-oidc

Repository-only deployment candidate for the VL Agent Control Plane live write boundary.

## Purpose

This function exposes only two OIDC-authenticated operations:

- `delegate_grant` -> `public.acp_delegate_agent_grant_nonprod`
- `revoke_grant` -> `public.acp_revoke_agent_grant`

It does **not** expose root-grant issuance, generic audit writes, production approval, production promotion, secret management, or direct table DML.

## Identity contract

Custom GitHub OIDC verification is required. If deployed, `verify_jwt=false` is intentional because this function verifies the GitHub JWT itself.

Required claims:

- issuer: `https://token.actions.githubusercontent.com`
- audience: `vrs-agent-control-plane`
- repository: `lundus88/fieldgis-reference`
- ref: `refs/heads/main`
- workflow: `.github/workflows/vl-agent-control-plane-admin.yml@refs/heads/main`

The referenced admin workflow is intentionally not introduced by this repository-only boundary PR. Until a separately reviewed workflow exists, the deployed function would fail closed for all workflow calls.

## Safety boundaries

- Delegation requires an existing parent grant.
- Delegation is limited to `development` or `staging` scope.
- `production.approve` and `production.promote` are rejected.
- DB triggers independently enforce capability, scope, budget, validity, cycle, and depth restrictions.
- State mutation and immutable audit evidence are committed atomically by the DB RPC.
- `service_role` has no direct DML on ACP private tables.
- No arbitrary audit-write RPC is granted to `service_role`.
- Authentication failures return 401; request failures return 400; policy/DB rejections return 409; unexpected internal failures return 500.

## Deployment status

Not deployed. Do not deploy until:

1. ACP store migration is explicitly approved and applied.
2. ACP live-boundary migration is explicitly approved and applied.
3. Parent/root grant bootstrap is separately reviewed and human-approved.
4. The dedicated admin workflow is reviewed and merged.
5. A staging-only end-to-end test proves OIDC -> RPC -> grant/audit persistence -> replay idempotency.
