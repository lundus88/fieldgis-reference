from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WF = (ROOT / ".github" / "workflows" / "lom-acp-migration-generation.yml").read_text()

assert "pull_request:" in WF
assert "contents: read" in WF
assert re.search(r"SUPABASE_CLI_VERSION:\s*2\.117\.0\b", WF)
assert 'supabase@${SUPABASE_CLI_VERSION}" migration new acp_read_agent_grant_chain_nonprod' in WF
assert 'supabase@${SUPABASE_CLI_VERSION}" migration new acp_lom_vps_parent_grant_renewal' in WF
assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in WF
assert "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f" in WF
assert "retention-days: 1" in WF

lower = WF.lower()
for forbidden in (
    "supabase_access_token",
    "supabase_db_password",
    "service_role",
    "secret_key",
    "supabase link",
    "db push",
    "db pull",
    "db reset",
    "migration up",
    "migration repair",
    "functions deploy",
    "apply_migration",
    "execute_sql",
):
    assert forbidden not in lower, f"remote/mutating operation forbidden in migration generator: {forbidden}"

print("LOM_ACP_MIGRATION_GENERATION_CONTRACT=PASS")
