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
assert by_id["vps_execution"]["status"] == "EXISTING"
assert "blocker" not in by_id["vps_execution"]
assert by_id["vps_execution"]["activation_state"] == "LIVE_VERIFIED_NON_PRODUCTION"
assert by_id["vps_execution"]["activation_evidence_verified"] is True
assert by_id["vps_execution"]["live_vps_verified"] is True
assert by_id["vps_execution"]["secure_ingress_verified"] is True
assert by_id["vps_execution"]["reboot_recovery_verified"] is True
assert by_id["vps_execution"]["operational_probe_verified"] is True
assert by_id["vps_execution"]["production_authority"] == "HUMAN_ONLY"
assert by_id["vps_execution"]["activation_boundary"] == "NON_PRODUCTION_ONLY"
assert by_id["vps_execution"]["runtime_host_policy"] == "VPS_ONLY"
assert by_id["vps_execution"]["canonical_runtime_node"] == "v103067"
assert by_id["vps_execution"]["office_workstation_role"] == "EXCLUDED_FROM_RUNTIME"
assert by_id["vps_execution"]["fallback_to_office_workstation"] == "FORBIDDEN"
assert by_id["autonomy_controller"]["authority"] == "DEFAULT_DENY"
assert "PROTECTED_MAIN_MERGE" in by_id["orchestration"]["human_gate"]
assert by_id["high_value_absorption"]["owner"] == "vl/lom-governance"
assert by_id["high_value_absorption"]["authority"] == "CLASSIFY_PROPOSE_PREPARE_PR"

maturity=cap["maturity_ladder"]
assert maturity["ordered_path"] == [
    "ECONOMIC_INTELLIGENCE",
    "SELF_HEALING",
    "REAL_REVENUE_PROOF",
    "INTERNATIONAL_VALIDATION",
    "EXTERNALLY_PROVEN_FRONTIER_INTELLIGENCE",
]
mstage={x["stage"]:x for x in maturity["progression"]}
assert mstage["ECONOMIC_INTELLIGENCE"]["status"] == "PARTIAL"
assert mstage["SELF_HEALING"]["status"] == "PARTIAL"
assert mstage["REAL_REVENUE_PROOF"]["status"] == "HOLD"
assert mstage["REAL_REVENUE_PROOF"]["synthetic_evidence_counts_as_completion"] is False
assert mstage["INTERNATIONAL_VALIDATION"]["status"] == "HOLD"
assert mstage["INTERNATIONAL_VALIDATION"]["worldwide_claim_inferred"] is False
assert mstage["INTERNATIONAL_VALIDATION"]["self_certification"] == "FORBIDDEN"
assert mstage["EXTERNALLY_PROVEN_FRONTIER_INTELLIGENCE"]["status"] == "HOLD"
assert mstage["EXTERNALLY_PROVEN_FRONTIER_INTELLIGENCE"]["world_best_claim"] == "FORBIDDEN_UNTIL_EXTERNALLY_PROVEN"
assert maturity["hard_invariants"]["human_sovereignty"] is True
assert maturity["hard_invariants"]["protected_main_merge"] == "HUMAN_ONLY"
assert maturity["hard_invariants"]["production_authority"] == "HUMAN_ONLY"

know=json.loads((ROOT/"vl/lom-knowledge-foundation/master-knowledge-registry.json").read_text())
assert know["duplicate_policy"] == "FLAG_ONLY_NO_AUTODELETE"
assert know["low_confidence_policy"] == "FAIL_CLOSED"
assert know["owner"] == "LOM Knowledge Librarian"

print("LOM_REGISTRY_TESTS=PASS")
