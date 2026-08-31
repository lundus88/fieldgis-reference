from pathlib import Path
import json
import sys

SQL = Path('vl/migrations/20260831_agent_control_plane_store.sql').read_text()
AUDIT_SCHEMA = json.loads(Path('vl/agent-control-plane/audit-event.schema.json').read_text())

checks = {
    'private grant store exists': 'private.agent_capability_grants' in SQL,
    'private audit store exists': 'private.agent_control_audit_events' in SQL,
    'grant identity uses agent_id': 'agent_id text not null' in SQL,
    'agent production capabilities prohibited': "principal_type <> 'agent'" in SQL and "production.approve" in SQL and "production.promote" in SQL,
    'delegation parent persisted': 'delegated_from_grant_id' in SQL,
    'grant activation persisted': 'valid_from timestamptz' in SQL,
    'grant expiry persisted': 'valid_until timestamptz' in SQL,
    'grant revocation persisted': 'revoked_at timestamptz' in SQL,
    'audit sequence unique': 'unique (action_id, event_seq)' in SQL,
    'audit chain fields exist': 'previous_event_digest' in SQL and 'event_digest' in SQL,
    'audit timestamp aligned': 'recorded_at timestamptz' in SQL,
    'audit requester aligned': 'requester jsonb not null' in SQL,
    'audit scope aligned': 'scope jsonb not null' in SQL,
    'audit replay event supported': "'idempotent_replay'" in SQL,
    'audit update blocked': 'trg_agent_control_audit_no_update' in SQL and 'before update' in SQL,
    'audit delete blocked': 'trg_agent_control_audit_no_delete' in SQL and 'before delete' in SQL,
    'audit mutation trigger fails closed': "raise exception 'agent_control_audit_events is append-only'" in SQL,
    'tables revoked from exposed roles': 'from public, anon, authenticated' in SQL,
    'no security definer introduced': 'security definer' not in SQL.lower(),
}

# Prevent the machine-readable audit contract and persistence schema from drifting apart.
required_fields = set(AUDIT_SCHEMA.get('required') or [])
for field in ('event_id', 'action_id', 'event_type', 'recorded_at', 'requester', 'capability', 'scope', 'input_digest', 'event_digest'):
    checks[f'audit schema requires {field}'] = field in required_fields
    checks[f'audit SQL persists {field}'] = field in SQL

schema_event_types = set(AUDIT_SCHEMA['properties']['event_type']['enum'])
for event_type in schema_event_types:
    checks[f'audit SQL supports event type {event_type}'] = repr(event_type) in SQL

failed = [name for name, ok in checks.items() if not ok]
result = {
    'schema_version': '1.0',
    'suite': 'agent-control-plane-persistence-contract',
    'status': 'PASS' if not failed else 'FAIL',
    'checks': checks,
    'production_applied': False,
}
print(json.dumps(result, indent=2, sort_keys=True))
if failed:
    for name in failed:
        print(f'FAIL: {name}', file=sys.stderr)
    raise SystemExit(1)
