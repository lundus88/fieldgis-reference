#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
p=subprocess.run([sys.executable, str(ROOT/"vl/lom-governance/validate_registries.py")], capture_output=True, text=True)
assert p.returncode == 0, p.stdout + p.stderr
assert "LOM_REGISTRY_VALIDATION=PASS" in p.stdout

cap=json.loads((ROOT/"vl/lom-governance/capability-registry.json").read_text())
by_id={x["id"]:x for x in cap["capabilities"]}
assert by_id["vps_execution"]["status"] == "BLOCKED"
assert by_id["vps_execution"]["blocker"] == "LIVE_VPS_CANARY_NOT_PROVEN"
assert by_id["vps_execution"]["runtime_host_policy"] == "VPS_ONLY"
assert by_id["vps_execution"]["canonical_runtime_node"] == "v103067"
assert by_id["vps_execution"]["office_workstation_role"] == "EXCLUDED_FROM_RUNTIME"
assert by_id["vps_execution"]["fallback_to_office_workstation"] == "FORBIDDEN"
assert "BPTSBH-G03-L011" in by_id["vps_execution"]["excluded_operational_dependencies"]
assert by_id["autonomy_controller"]["authority"] == "DEFAULT_DENY"
assert "PROTECTED_MAIN_MERGE" in by_id["orchestration"]["human_gate"]
assert by_id["high_value_absorption"]["owner"] == "vl/lom-governance"
assert by_id["high_value_absorption"]["authority"] == "CLASSIFY_PROPOSE_PREPARE_PR"

know=json.loads((ROOT/"vl/lom-knowledge-foundation/master-knowledge-registry.json").read_text())
assert know["duplicate_policy"] == "FLAG_ONLY_NO_AUTODELETE"
assert know["low_confidence_policy"] == "FAIL_CLOSED"
assert know["owner"] == "LOM Knowledge Librarian"

print("LOM_REGISTRY_TESTS=PASS")
