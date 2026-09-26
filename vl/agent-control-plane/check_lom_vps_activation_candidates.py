from pathlib import Path
import sys

ROOT = Path(__file__).parent / "sql-candidates"
READ = (ROOT / "acp_read_agent_grant_chain_nonprod.sql").read_text()
PARENT = (ROOT / "acp_lom_vps_parent_grant_renewal.sql").read_text()
BUDGET = (ROOT / "acp_delegation_budget_inheritance_hardening.sql").read_text()

errors = []

private_marker = "create or replace function private.acp_read_agent_grant_chain_nonprod_impl"
public_marker = "create or replace function public.acp_read_agent_grant_chain_nonprod"
if private_marker not in READ.lower():
    errors.append("read RPC missing private implementation")
if public_marker not in READ.lower():
    errors.append("read RPC missing public wrapper")

if private_marker in READ.lower() and public_marker in READ.lower():
    lower = READ.lower()
    private_start = lower.index(private_marker)
    public_start = lower.index(public_marker)
    private_sql = lower[private_start:public_start]
    public_sql = lower[public_start:]
    if "security definer" not in private_sql:
        errors.append("private implementation must be SECURITY DEFINER")
    if "security invoker" not in public_sql:
        errors.append("public wrapper must be SECURITY INVOKER")
    if "security definer" in public_sql:
        errors.append("public wrapper must not be SECURITY DEFINER")
    if "private.agent_capability_grants" in public_sql:
        errors.append("public wrapper must not access the private grant table directly")

required_read = [
    "set search_path = ''",
    "stable",
    "private.agent_capability_grants",
    "p_target_environment not in ('development', 'staging')",
    "principal_type <> 'agent'",
    "production.approve",
    "production.promote",
    "c.depth < 16",
    "revoke all on function private.acp_read_agent_grant_chain_nonprod_impl",
    "grant execute on function private.acp_read_agent_grant_chain_nonprod_impl",
    "revoke all on function public.acp_read_agent_grant_chain_nonprod",
    "grant execute on function public.acp_read_agent_grant_chain_nonprod",
    "from public, anon, authenticated",
    "to service_role",
]
for marker in required_read:
    if marker.lower() not in READ.lower():
        errors.append(f"read RPC missing required marker: {marker}")

forbidden_read = [
    "insert into",
    "update private.agent_capability_grants",
    "delete from",
    "grant select on private.agent_capability_grants",
    "execute format(",
    "production.approve','factory",
]
for marker in forbidden_read:
    if marker.lower() in READ.lower():
        errors.append(f"read RPC contains forbidden marker: {marker}")

required_parent = [
    "p.slug = 'fieldgis-reference'",
    "e.kind = 'staging'",
    "e.status = 'ready'",
    "array['factory.plan']::text[]",
    "'timeout_seconds', 60",
    "'max_retries', 0",
    "'max_cost_minor', 0",
    "interval '24 hours'",
    "delegated_from_grant_id is null",
    "human-approved:lom-direct-vps-activation",
    "APPROVE LOM VPS STAGING PARENT GRANT",
    "private.agent_control_audit_events",
]
for marker in required_parent:
    if marker.lower() not in PARENT.lower():
        errors.append(f"parent renewal missing required marker: {marker}")

required_budget = [
    "create or replace function private.validate_agent_capability_grant()",
    "parent_row.budget ? key and not (new.budget ? key)",
    "ACP delegated budget missing parent bound for %",
    "ACP delegated budget exceeds parent for %",
]
for marker in required_budget:
    if marker.lower() not in BUDGET.lower():
        errors.append(f"budget hardening missing required marker: {marker}")

forbidden_parent = [
    "production.approve",
    "production.promote",
    "connector.invoke",
    "factory.enqueue",
    "release.request_approval",
    "grant all",
    "service_role",
    "g.capabilities @> array['factory.plan']::text[]",
]
for marker in forbidden_parent:
    if marker.lower() in PARENT.lower():
        errors.append(f"parent renewal contains forbidden marker: {marker}")

if "CANDIDATE ONLY" not in READ or "CANDIDATE ONLY" not in PARENT or "CANDIDATE ONLY" not in BUDGET:
    errors.append("candidate-only status must be explicit")
if "DO NOT APPLY DIRECTLY" not in READ or "DO NOT APPLY DIRECTLY" not in PARENT or "DO NOT APPLY DIRECTLY" not in BUDGET:
    errors.append("direct-apply prohibition must be explicit")

if errors:
    print("LOM VPS ACP ACTIVATION CANDIDATES: FAIL")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("LOM VPS ACP ACTIVATION CANDIDATES: PASS")
