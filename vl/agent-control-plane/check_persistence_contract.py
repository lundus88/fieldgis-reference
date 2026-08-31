from pathlib import Path
import sys

SQL = Path('vl/migrations/20260831_agent_control_plane_store.sql').read_text()

checks = {
    'private grant store exists': 'private.agent_capability_grants' in SQL,
    'private audit store exists': 'private.agent_control_audit_events' in SQL,
    'agent production capabilities prohibited': "principal_type <> 'agent'" in SQL and "production.approve" in SQL and "production.promote" in SQL,
    'delegation parent persisted': 'delegated_from_grant_id' in SQL,
    'grant expiry persisted': 'valid_until timestamptz' in SQL,
    'grant revocation persisted': 'revoked_at timestamptz' in SQL,
    'audit sequence unique': 'unique (action_id, event_seq)' in SQL,
    'audit chain fields exist': 'previous_event_hash' in SQL and 'event_hash' in SQL,
    'audit update blocked': 'trg_agent_control_audit_no_update' in SQL and 'before update' in SQL,
    'audit delete blocked': 'trg_agent_control_audit_no_delete' in SQL and 'before delete' in SQL,
    'audit mutation trigger fails closed': "raise exception 'agent_control_audit_events is append-only'" in SQL,
    'tables revoked from exposed roles': 'from public, anon, authenticated' in SQL,
    'no security definer introduced': 'security definer' not in SQL.lower(),
}

failed = [name for name, ok in checks.items() if not ok]
result = {
    'schema_version': '1.0',
    'suite': 'agent-control-plane-persistence-contract',
    'status': 'PASS' if not failed else 'FAIL',
    'checks': checks,
    'production_applied': False,
}
print(result)
if failed:
    for name in failed:
        print(f'FAIL: {name}', file=sys.stderr)
    raise SystemExit(1)
