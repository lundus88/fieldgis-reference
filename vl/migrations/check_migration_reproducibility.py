#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "vl" / "migrations"
MANIFEST = MIGRATIONS / "reproducibility_manifest.json"

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
assert manifest["schema"] == "vl.migration-reproducibility/1"
policy = manifest["policy"]
assert policy["historical_migrations_are_immutable"] is True
assert policy["synthetic_certification_evidence_for_replay"] is False
assert policy["production_schema_mutation_during_history_repair"] is False
assert policy["tracking_only_repair_requires_exact_schema_parity"] is True
assert policy["fresh_dev_replay_required_before_rollout"] is True

known = manifest["known_remote_history_prerequisites"]
assert len(known) >= 8, "known migration provenance gaps unexpectedly missing"
for entry in known:
    assert entry["object"].strip()
    assert entry["first_observed_blocker"].strip()
    assert "missing" in entry["status"].lower() or "absent" in entry["status"].lower()

for entry in manifest["historical_data_dependent_migrations"]:
    path = ROOT / entry["file"]
    assert path.exists(), f"documented data-dependent migration missing: {entry['file']}"
    sql = path.read_text(encoding="utf-8").lower()
    assert "builder_certification" in sql, f"manifest classification drifted: {entry['file']}"
    assert "raise exception" in sql, f"historical fail-closed behavior unexpectedly removed: {entry['file']}"
    assert "synthetic" not in sql, f"historical migration must never synthesize evidence: {entry['file']}"

required_gates = set(manifest["required_recovery_gates"])
for gate in {
    "canonical_remote_schema_pull",
    "schema_parity_review",
    "migration_history_diff_review",
    "tracking_only_history_repair_if_schema_exactly_matches",
    "fresh_data_less_dev_replay",
    "operational_reconciliation_regression",
    "read_only_production_non_mutation_verification",
}:
    assert gate in required_gates, f"missing recovery gate: {gate}"

# Recovery/baseline files must not manufacture positive certification evidence or
# production authority. This guard applies to present and future recovery files.
recovery_name = re.compile(r"(reproduc|baseline|history_repair|schema_pull|recovery)", re.I)
for path in MIGRATIONS.glob("*.sql"):
    if not recovery_name.search(path.name):
        continue
    sql = path.read_text(encoding="utf-8").lower()
    forbidden = [
        r"insert\s+into\s+public\.builder_certification_evidence",
        r"update\s+public\.builder_certification_evidence",
        r"set\s+evidence_status\s*=\s*'pass'",
        r"set\s+status\s*=\s*'approved'",
        r"set\s+status\s*=\s*'deployed'",
        r"set\s+state\s*=\s*'certified'",
        r"set\s+state\s*=\s*'succeeded'",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, sql, re.I), (
            f"recovery migration may manufacture positive authority/evidence: {path.name}: {pattern}"
        )

print("VL_MIGRATION_REPRODUCIBILITY_CONTRACT=PASS")
