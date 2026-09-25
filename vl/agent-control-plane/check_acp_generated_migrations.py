from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
manifest_path = ROOT / "vl" / "migrations" / "acp_direct_vps_migration_generation_20260925.json"
manifest = json.loads(manifest_path.read_text())

assert manifest["schema"] == "vl.acp-migration-generation-evidence/1"
assert manifest["supabase_cli_version"] == "2.117.0"
assert manifest["remote_project_access"] is False
assert manifest["credentials_used"] is False
assert manifest["live_database_mutation"] is False

candidate_map = {
    "20260925024934_acp_read_agent_grant_chain_nonprod.sql":
        ROOT / "vl" / "agent-control-plane" / "sql-candidates" / "acp_read_agent_grant_chain_nonprod.sql",
    "20260925024937_acp_lom_vps_parent_grant_renewal.sql":
        ROOT / "vl" / "agent-control-plane" / "sql-candidates" / "acp_lom_vps_parent_grant_renewal.sql",
}

for entry in manifest["migrations"]:
    repo_path = ROOT / entry["repository_path"]
    assert repo_path.exists(), f"missing generated migration: {repo_path}"
    basename = repo_path.name
    assert basename in candidate_map, f"unexpected generated migration: {basename}"
    raw = repo_path.read_bytes()
    candidate = candidate_map[basename].read_bytes()
    assert raw == candidate, f"generated migration drifted from reviewed candidate: {basename}"
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == entry["sha256"], f"sha256 mismatch for {basename}"
    assert entry["apply_status"] == "NOT_APPLIED"
    assert entry["human_gate_required"] is True

print("LOM_ACP_GENERATED_MIGRATIONS=PASS")
