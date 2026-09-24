from pathlib import Path
import sys

ROOT = Path(__file__).parent / "sql-candidates"
READ = (ROOT / "acp_read_agent_grant_chain_nonprod.sql").read_text()
PARENT = (ROOT / "acp_lom_vps_parent_grant_renewal.sql").read_text()

errors = []

required_read = [
    "security definer",
    "set search_path = ''",
    "stable",
    "private.agent_capability_grants",
    "p_target_environment not in ('development', 'staging')",
    "principal_type <> 'agent'",
    "production.approve",
    "production.promote",
    "c.depth < 16",
    "revoke all on function public.acp_read_agent_grant_chain_nonprod",
    "from public, anon, authenticated",
    "grant execute on function public.acp_read_agent_grant_chain_nonprod",
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

forbidden_parent = [
    "production.approve",
    "production.promote",
    "connector.invoke",
    "factory.enqueue",
    "release.request_approval",
    "grant all",
    "service_role",
]
for marker in forbidden_parent:
    if marker.lower() in PARENT.lower():
        errors.append(f"parent renewal contains forbidden marker: {marker}")

if "CANDIDATE ONLY" not in READ or "CANDIDATE ONLY" not in PARENT:
    errors.append("candidate-only status must be explicit")
if "DO NOT APPLY DIRECTLY" not in READ or "DO NOT APPLY DIRECTLY" not in PARENT:
    errors.append("direct-apply prohibition must be explicit")

if errors:
    print("LOM VPS ACP ACTIVATION CANDIDATES: FAIL")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("LOM VPS ACP ACTIVATION CANDIDATES: PASS")
