#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "vl-schema-capture-evidence.yml"
FINGERPRINT = ROOT / "vl" / "migrations" / "remote_schema_fingerprint_2026-09-10.json"

text = WORKFLOW.read_text(encoding="utf-8")
lower = text.lower()

# Capture is opt-in/manual only and least privilege.
assert "workflow_dispatch:" in text
assert "pull_request:" not in text
assert "\n  push:" not in text
assert "contents: read" in text
assert "supabase_access_token: ${{ secrets.supabase_access_token }}" in lower
assert "supabase_db_password: ${{ secrets.supabase_db_password }}" in lower

# Toolchain and third-party actions are pinned.
assert re.search(r"SUPABASE_CLI_VERSION:\s*2\.117\.0\b", text)
assert "supabase@${SUPABASE_CLI_VERSION}" in text
assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in text
assert "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f" in text

# The only remote database operations allowed here are read-only capture operations.
for required in ("db dump --linked", "migration fetch", "retention-days: 1"):
    assert required in text, f"missing capture safeguard: {required}"

for forbidden in (
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
    assert forbidden not in lower, f"mutating or data-export command forbidden in capture workflow: {forbidden}"

assert "Potential credential material detected" in text
assert "artifact upload blocked" in text

fp = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
assert fp["schema"] == "vl.remote-schema-fingerprint/1"
assert fp["capture_mode"] == "read_only_metadata"
assert fp["contains_production_rows"] is False
assert fp["migration_history"]["count"] == 166
assert fp["migration_history"]["first_version"] == "20260825085858"
assert fp["migration_history"]["last_version"] == "20260901034112"
for key in ("chain_sha256",):
    assert re.fullmatch(r"[0-9a-f]{64}", fp["migration_history"][key])
for section in ("functions", "columns", "constraints", "indexes", "policies"):
    entry = fp["schema_fingerprint"][section]
    assert entry["count"] > 0
    assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])

gov = fp["governance"]
assert gov["authoritative_schema_dump_required_before_history_repair"] is True
assert gov["migration_history_repair_performed"] is False
assert gov["production_schema_mutation_performed"] is False
assert gov["synthetic_certification_evidence_created"] is False

print("VL_SCHEMA_CAPTURE_EVIDENCE_CONTRACT=PASS")
