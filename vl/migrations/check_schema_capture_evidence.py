#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "vl-schema-capture-evidence.yml"
FINGERPRINT = ROOT / "vl" / "migrations" / "remote_schema_fingerprint_2026-10-04.json"
BASELINE_DIR = ROOT / "vl" / "migrations" / "baselines" / "2026-10-04"
RAW_SCHEMA = BASELINE_DIR / "remote_schema.sql"
BOOTSTRAP = BASELINE_DIR / "bootstrap.sql"

text = WORKFLOW.read_text(encoding="utf-8")
lower = text.lower()

# Capture remains opt-in/manual. Baseline promotion is a separate explicit opt-in
# and is hard-bound to the recovery branch.
assert "workflow_dispatch:" in text
assert "pull_request:" not in text
assert "\n  push:" not in text
assert "promote_baseline:" in text
assert "default: false" in lower
assert text.count("contents: write") == 1
assert "contents: read" in text
assert "github.ref_name == 'fix/vl-migration-reproducibility-refresh-20261004'" in text
assert 'test "$GITHUB_REF_NAME" = "fix/vl-migration-reproducibility-refresh-20261004"' in text

# Capture does not require a Supabase Management API access token.
assert "supabase_access_token" not in lower
assert "supabase_db_password: ${{ secrets.supabase_db_password }}" in lower

# Toolchain and third-party actions are pinned.
assert re.search(r"SUPABASE_CLI_VERSION:\s*2\.117\.0\b", text)
assert "supabase@${SUPABASE_CLI_VERSION}" in text
assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in text
assert "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f" in text
assert "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093" in text

# Remote database work is read-only and goes through the IPv4 transaction pooler.
for required in (
    'db dump --db-url "$DB_URL"',
    'migration fetch --db-url "$DB_URL"',
    "sslmode=require",
    "${VL_SUPABASE_DB_HOST}:${VL_SUPABASE_DB_PORT}",
    "${VL_SUPABASE_DB_USER}",
    "VL_SUPABASE_DB_HOST: aws-0-ap-southeast-1.pooler.supabase.com",
    "VL_SUPABASE_DB_PORT: 6543",
    "VL_SUPABASE_DB_USER: postgres.wczelfmnqpgzfdszxubl",
    "retention-days: 1",
):
    assert required in text, f"missing capture safeguard: {required}"

for forbidden in (
    "supabase link",
    "--linked",
    "db push",
    "db pull",
    "db reset",
    "migration repair",
    "migration up",
    "functions deploy",
    "--data-only",
    "--role-only",
    "apply_migration",
    "merge_branch",
):
    assert forbidden not in lower, f"mutating or privilege-expanding DB command forbidden: {forbidden}"

assert '::add-mask::${ENCODED_DB_PASSWORD}' in text
assert '::add-mask::${DB_URL}' in text
assert "Potential credential material detected" in text
assert "artifact upload blocked" in text

# Promotion can only preserve the already reviewed capture on the recovery branch.
assert "50d426da6ad13641d5ef3d44b0a3fa84ea61828e4c549d4fef6faa5ef812afb5" in text
assert 'wc -l' in text and '= "174"' in text
assert "remote_schema.sql.gz" in text
assert "fetched_migrations.tar.gz" in text
assert "SHA256SUMS.txt" in text
assert "PROVENANCE.json" in text
assert "git push origin" in text

fp = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
assert fp["schema"] == "vl.remote-schema-fingerprint/1"
assert fp["capture"]["schema_only"] is True
assert fp["capture"]["contains_production_rows"] is False
assert fp["capture"]["credential_scan_passed"] is True
assert fp["migration_history"]["count"] == 174
assert fp["migration_history"]["first_version"] == "20260825085858"
assert fp["migration_history"]["last_version"] == "20261004003624"
assert re.fullmatch(r"[0-9a-f]{64}", fp["migration_history"]["metadata_chain_sha256"])
assert re.fullmatch(r"[0-9a-f]{64}", fp["capture"]["remote_schema_sha256"])
assert re.fullmatch(r"[0-9a-f]{64}", fp["capture"]["sha256_manifest_sha256"])

for section in ("functions", "columns", "constraints", "indexes", "policies"):
    assert fp["schema_fingerprint"][section] > 0

parity = fp["parity_findings"]
assert parity["repo_sql_files"] == 37
assert parity["remote_migrations"] == 174
assert parity["vl_cert_health_present_in_schema"] is True
assert parity["vl_cert_health_migration_hits"] == 0
assert parity["legacy_chain_replay_is_authoritative"] is False
assert parity["canonical_schema_baseline_required"] is True

gov = fp["governance"]
assert gov["migration_history_repair_performed"] is False
assert gov["production_schema_mutation_performed"] is False
assert gov["historical_migrations_edited"] is False
assert gov["synthetic_certification_evidence_created"] is False
assert gov["production_activation_hold"] is True

raw_schema = RAW_SCHEMA.read_bytes()
assert __import__("hashlib").sha256(raw_schema).hexdigest() == "50d426da6ad13641d5ef3d44b0a3fa84ea61828e4c549d4fef6faa5ef812afb5"
bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
assert "NEVER apply this file to Production" in bootstrap
assert "DROP SCHEMA IF EXISTS private CASCADE;" in bootstrap
assert "DROP SCHEMA IF EXISTS public CASCADE;" in bootstrap
assert "CREATE SCHEMA public AUTHORIZATION postgres;" in bootstrap
assert "CREATE SCHEMA private AUTHORIZATION postgres;" in bootstrap
assert bootstrap.endswith(RAW_SCHEMA.read_text(encoding="utf-8"))

print("VL_SCHEMA_CAPTURE_EVIDENCE_CONTRACT=PASS")
