from pathlib import Path
import json
import sys

WORKFLOW = Path('.github/workflows/vl-agent-control-plane-admin.yml').read_text()
NEGATIVE = Path('.github/workflows/vl-acp-edge-negative-auth.yml').read_text()

checks = {
    'admin workflow dispatch only': 'workflow_dispatch:' in WORKFLOW and 'schedule:' not in WORKFLOW and 'push:' not in WORKFLOW and 'pull_request:' not in WORKFLOW,
    'admin contents read': 'contents: read' in WORKFLOW,
    'admin id token write': 'id-token: write' in WORKFLOW,
    'exact oidc audience': 'audience=vrs-agent-control-plane' in WORKFLOW,
    'exact edge endpoint': 'vrs-agent-control-oidc' in WORKFLOW,
    'no supabase service role secret': 'SUPABASE_SERVICE_ROLE_KEY' not in WORKFLOW and 'service_role' not in WORKFLOW.lower(),
    'no root grant operation': 'root_grant' not in WORKFLOW.lower() and 'create_root' not in WORKFLOW.lower() and 'issue_root' not in WORKFLOW.lower(),
    'only delegate and revoke operations': '- delegate_grant' in WORKFLOW and '- revoke_grant' in WORKFLOW,
    'production target unavailable': '\n          - production\n' not in WORKFLOW,
    'production capabilities explicitly rejected': "('production.approve','production.promote')" in WORKFLOW,
    'bounded target options': '- staging' in WORKFLOW and '- development' in WORKFLOW,
    'concurrency serialization': 'group: vl-agent-control-plane-admin' in WORKFLOW and 'cancel-in-progress: false' in WORKFLOW,
    'negative auth has no id token permission': 'id-token: write' not in NEGATIVE,
    'negative auth requires 401': NEGATIVE.count('test "$code" = "401"') == 2,
    'negative auth checks no oidc authority': 'ACTIONS_ID_TOKEN_REQUEST_URL' in NEGATIVE and 'ACTIONS_ID_TOKEN_REQUEST_TOKEN' in NEGATIVE,
}

failed=[name for name, ok in checks.items() if not ok]
print(json.dumps({
    'schema_version':'1.0',
    'suite':'agent-control-plane-admin-workflow',
    'status':'PASS' if not failed else 'FAIL',
    'root_grant_bootstrap':False,
    'production_capability':False,
    'checks':checks,
}, indent=2, sort_keys=True))
if failed:
    for name in failed:
        print(f'FAIL: {name}', file=sys.stderr)
    raise SystemExit(1)
