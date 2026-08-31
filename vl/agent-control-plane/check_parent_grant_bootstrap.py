from pathlib import Path
import sys

sql = Path('vl/migrations/20260901_agent_control_plane_parent_grant_bootstrap.sql').read_text()

required = [
    "'vl-golden-api-20260826111827'",
    "'staging'",
    "array['spec.read']::text[]",
    "'timeout_seconds', 60",
    "'max_retries', 0",
    "'max_cost_minor', 0",
    "interval '24 hours'",
    "'founder-approved:gate-e:2026-09-01'",
    "'APPROVE ACP PARENT GRANT BOOTSTRAP'",
    "'minimum-staging-canary'",
    "requires empty grant store",
    "requires empty audit store",
]
forbidden = [
    'production.approve',
    'production.promote',
    'factory.enqueue',
    'certification.propose',
    'release.request_approval',
    'SUPABASE_SERVICE_ROLE_KEY',
    'service_role',
    'grant all',
]

errors=[]
for marker in required:
    if marker not in sql:
        errors.append(f'missing required bootstrap marker: {marker}')
for marker in forbidden:
    if marker.lower() in sql.lower():
        errors.append(f'forbidden bootstrap marker present: {marker}')
if 'p.slug =' not in sql or 'p.id' not in sql:
    errors.append('bootstrap must resolve project by stable slug, not hardcoded project UUID')
if "delegated_from_grant_id" not in sql or "null" not in sql:
    errors.append('bootstrap parent must remain a root/parent grant with no runtime delegation source')
if 'private.agent_control_audit_events' not in sql:
    errors.append('bootstrap must append audit evidence in the same migration')

if errors:
    print('ACP PARENT GRANT BOOTSTRAP CONTRACT: FAIL')
    for error in errors:
        print(f'- {error}')
    sys.exit(1)
print('ACP PARENT GRANT BOOTSTRAP CONTRACT: PASS')
