import json
from pathlib import Path

from validate_canary import validate_canary

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "vps-canary-contract.json").read_text(encoding="utf-8"))
NOW = 2_000_000_000


def evidence(result="PASS"):
    return {
        "schema": "lom.vps-canary-evidence/1",
        "evidence_class": "SYNTHETIC_VALIDATOR_FIXTURE",
        "checks": [
            {
                "name": name,
                "result": result,
                "source_reference": f"synthetic:{name}",
                "observed_at_epoch": NOW,
            }
            for name in CONTRACT["required_checks"]
        ],
    }


def test_complete_synthetic_fixture_proves_validator_only():
    result = validate_canary(CONTRACT, evidence())
    assert result["status"] == "PASS"
    assert result["live_vps_verified"] is False
    assert result["activation_status"] == "HOLD"


def live_evidence():
    e = evidence()
    e["evidence_class"] = "LIVE_VPS_CANARY"
    e["node_attestation"] = {
        "node_id": "node-01",
        "environment_class": "NON_PRODUCTION_VPS",
        "operator_confirmed": True,
        "uid": 1001,
        "hostname_hash": "sha256:" + "1" * 64,
        "boot_id_hash": "sha256:" + "2" * 64,
        "collector_version": "1.0",
        "repo_sha": "a" * 40,
        "observed_at_epoch": NOW,
    }
    for row in e["checks"]:
        row["source_reference"] = f"vps:node-01:{row['name']}"
    return e


def test_live_vps_evidence_can_activate_only_with_bound_attestation():
    result = validate_canary(CONTRACT, live_evidence())
    assert result["status"] == "PASS"
    assert result["attestation_valid"] is True
    assert result["live_vps_verified"] is True
    assert result["activation_status"] == "READY"
    assert result["observed_at_epoch"] == NOW


def test_live_class_without_attestation_holds():
    e = evidence()
    e["evidence_class"] = "LIVE_VPS_CANARY"
    for row in e["checks"]:
        row["source_reference"] = f"vps:node-01:{row['name']}"
    result = validate_canary(CONTRACT, e)
    assert result["status"] == "HOLD"
    assert result["live_vps_verified"] is False
    assert "LIVE_NODE_ATTESTATION_INVALID" in result["violations"]


def test_live_sources_must_bind_to_attested_node():
    e = live_evidence()
    e["checks"][0]["source_reference"] = "vps:other-node:unprivileged_os_identity"
    result = validate_canary(CONTRACT, e)
    assert result["status"] == "HOLD"
    assert result["live_vps_verified"] is False
    assert "LIVE_SOURCE_BINDING_INVALID" in result["violations"]


def test_missing_check_holds():
    e = evidence()
    e["checks"] = e["checks"][:-1]
    result = validate_canary(CONTRACT, e)
    assert result["status"] == "HOLD"
    assert result["missing_checks"]


def test_not_run_holds():
    e = evidence()
    e["checks"][0]["result"] = "NOT_RUN"
    result = validate_canary(CONTRACT, e)
    assert result["status"] == "HOLD"
    assert result["not_run_checks"]


def test_failed_check_holds():
    e = evidence()
    e["checks"][0]["result"] = "FAIL"
    result = validate_canary(CONTRACT, e)
    assert result["status"] == "HOLD"
    assert result["failed_checks"]


def test_duplicate_check_holds():
    e = evidence()
    e["checks"].append(dict(e["checks"][0]))
    result = validate_canary(CONTRACT, e)
    assert result["status"] == "HOLD"
    assert "DUPLICATE_OR_MISSING_CHECK" in result["violations"]


def test_unknown_check_holds():
    e = evidence()
    e["checks"].append({
        "name": "magic_check",
        "result": "PASS",
        "source_reference": "synthetic:magic",
        "observed_at_epoch": NOW,
    })
    result = validate_canary(CONTRACT, e)
    assert result["status"] == "HOLD"
    assert result["unknown_checks"] == ["magic_check"]


def test_weakened_connector_boundary_holds():
    contract = json.loads(json.dumps(CONTRACT))
    contract["authority"]["connector_execution_during_p0_canary"] = "ENABLED"
    result = validate_canary(contract, evidence())
    assert result["status"] == "HOLD"
    assert result["reason"] == "CONNECTOR_CANARY_BOUNDARY_WEAKENED"


def test_weakened_live_evidence_contract_holds():
    contract = json.loads(json.dumps(CONTRACT))
    contract["live_evidence_requirements"]["synthetic_sources_forbidden"] = False
    result = validate_canary(contract, evidence())
    assert result["status"] == "HOLD"
    assert result["reason"] == "LIVE_EVIDENCE_CONTRACT_INVALID"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} VPS Canary Contract tests")
