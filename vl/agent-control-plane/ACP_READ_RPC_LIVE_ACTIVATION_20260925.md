# ACP Read-Only Resolver — Live Activation Evidence

Status: **READ RPC LIVE / PARENT GRANT HOLD / VPS ACTIVATION HOLD**

On 2026-09-25 the first approved ACP migration was applied to `vrs-core`:

- remote migration: `20260925025656_acp_read_agent_grant_chain_nonprod`
- repository source: `vl/migrations/20260925024934_acp_read_agent_grant_chain_nonprod.sql`

Post-apply verification:

- private implementation exists as `SECURITY DEFINER`;
- public wrapper exists as `SECURITY INVOKER`;
- both use an empty `search_path`;
- `anon` and `authenticated` cannot execute either function;
- `service_role` can execute but still has no direct `SELECT` on `private.agent_capability_grants`;
- `production` target requests are rejected;
- missing grants are rejected;
- security/performance advisors show no new blocking finding relative to the pre-apply baseline.

Still HOLD:

- parent grant migration has not been applied;
- no active non-production grant exists;
- no active `lom-vps-runner` grant exists;
- `vrs-agent-grant-resolver` Edge Function is not deployed;
- VPS activation remains human-gated.
