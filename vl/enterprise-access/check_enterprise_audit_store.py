from pathlib import Path

SQL = Path(__file__).with_name('enterprise-audit-store.sql').read_text()

required = [
    'create table if not exists vl_enterprise.session_visibility',
    'create table if not exists vl_enterprise.audit_events',
    'alter table vl_enterprise.session_visibility enable row level security',
    'alter table vl_enterprise.audit_events enable row level security',
    'session_self_or_workspace_auditor_select',
    'audit_workspace_scoped_select',
    'audit_trusted_writer_insert',
    "current_setting('vl.audit_writer', true) = 'true'",
    "current_setting('vl.workspace_id', true)",
    "current_setting('vl.actor_id', true)",
    'on update restrict on delete restrict',
    'audit_metadata_no_common_secret_keys',
]

missing = [item for item in required if item not in SQL]
if missing:
    raise SystemExit(f'MISSING_REQUIRED_AUDIT_STORE_CONTRACT: {missing}')

for forbidden in (
    'grant all',
    'disable row level security',
    'security definer',
    'service_role',
    'production.approve',
    'merge.execute',
):
    if forbidden in SQL.lower():
        raise SystemExit(f'FORBIDDEN_AUDIT_STORE_PATTERN: {forbidden}')

# The audit table must remain append-only at this contract layer.
for forbidden_statement in (
    'create policy audit_update',
    'create policy audit_delete',
    'for update',
    'for delete',
):
    if forbidden_statement in SQL.lower():
        raise SystemExit(f'APPEND_ONLY_CONTRACT_VIOLATION: {forbidden_statement}')

print('ENTERPRISE_AUDIT_STORE_CONTRACT: PASS')
