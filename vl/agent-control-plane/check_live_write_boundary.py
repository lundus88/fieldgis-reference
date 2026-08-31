from pathlib import Path
import json
import sys

SQL = Path('vl/migrations/20260901_agent_control_plane_live_boundary.sql').read_text()
STORE = Path('vl/migrations/20260831_agent_control_plane_store.sql').read_text()
EDGE = Path('vl/functions/vrs-agent-control-oidc/index.ts').read_text()
README = Path('vl/functions/vrs-agent-control-oidc/README.md').read_text()

checks = {
    'store keeps service_role off direct grant DML': 'revoke all on table private.agent_capability_grants from public, anon, authenticated, service_role' in STORE,
    'store keeps service_role off direct audit DML': 'revoke all on table private.agent_control_audit_events from public, anon, authenticated, service_role' in STORE,
    'delegation RPC exists': 'public.acp_delegate_agent_grant_nonprod' in SQL,
    'revocation RPC exists': 'public.acp_revoke_agent_grant' in SQL,
    'boundary RPCs are security definer': SQL.lower().count('security definer') == 2,
    'fixed search_path exists': SQL.count('set search_path = pg_catalog, private, extensions') >= 3,
    'runtime root grant issuance prohibited': 'ACP runtime root grant issuance is prohibited' in SQL,
    'production capability delegation prohibited': "array['production.approve','production.promote']" in SQL,
    'nonproduction target required': "not in ('development', 'staging')" in SQL,
    'delegation is parent bound': 'p_parent_grant_id uuid' in SQL and 'delegated_from_grant_id' in SQL,
    'grant mutation audit is atomic': 'private.acp_append_admin_audit_event' in SQL and 'insert into private.agent_capability_grants' in SQL,
    'revoke mutation audit is atomic': 'update private.agent_capability_grants' in SQL and "'acp.revoke_agent_grant'" in SQL,
    'audit helper not executable by service_role': 'private.acp_append_admin_audit_event' in SQL and 'from public, anon, authenticated, service_role' in SQL,
    'only narrow RPC execute granted': SQL.count('grant execute on function public.acp_') == 2,
    'no generic public audit writer': 'public.acp_append' not in SQL,
    'edge exact OIDC audience': 'const AUDIENCE = "vrs-agent-control-plane"' in EDGE,
    'edge exact repository': 'const REPOSITORY = "lundus88/fieldgis-reference"' in EDGE,
    'edge exact main ref': 'const MAIN_REF = "refs/heads/main"' in EDGE,
    'edge exact admin workflow': '.github/workflows/vl-agent-control-plane-admin.yml@refs/heads/main' in EDGE,
    'edge uses only two RPC calls': EDGE.count('sb.rpc(') == 2,
    'edge uses delegate RPC': 'sb.rpc("acp_delegate_agent_grant_nonprod"' in EDGE,
    'edge uses revoke RPC': 'sb.rpc("acp_revoke_agent_grant"' in EDGE,
    'edge does not use direct table access': '.from(' not in EDGE,
    'edge rejects production capabilities': 'production capability delegation prohibited' in EDGE,
    'edge rejects production target': 'ACP live boundary is non-production only' in EDGE,
    'auth failures are separate 401': 'instanceof AuthError' in EDGE and '}, 401)' in EDGE,
    'policy DB rejection is 409': 'ACP_POLICY_REJECTED' in EDGE and '}, 409)' in EDGE,
    'unexpected internal error is 500': 'ACP_INTERNAL_FAILURE' in EDGE and '}, 500)' in EDGE,
    'service role secret is not returned': 'SERVICE_ROLE' in EDGE and 'service_role_key: SERVICE_ROLE' not in EDGE and 'serviceRole: SERVICE_ROLE' not in EDGE,
    'admin workflow intentionally absent': 'intentionally not introduced' in README,
    'deployment remains blocked': 'Not deployed.' in README,
}

for forbidden in ('acp_create_root_grant', 'acp_issue_root_grant', 'acp_append_audit_event'):
    checks[f'forbidden public expansion absent: {forbidden}'] = f'public.{forbidden}' not in SQL

failed = [name for name, ok in checks.items() if not ok]
result = {
    'schema_version': '1.0',
    'suite': 'agent-control-plane-live-write-boundary',
    'status': 'PASS' if not failed else 'FAIL',
    'production_applied': False,
    'edge_deployed': False,
    'checks': checks,
}
print(json.dumps(result, indent=2, sort_keys=True))
if failed:
    for name in failed:
        print(f'FAIL: {name}', file=sys.stderr)
    raise SystemExit(1)
