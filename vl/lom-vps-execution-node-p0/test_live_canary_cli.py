import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "vps-canary-contract.json").read_text(encoding="utf-8"))
NOW = 1_800_000_000


def live_evidence():
    return {
        "schema": "lom.vps-canary-evidence/1",
        "evidence_class": "LIVE_VPS_CANARY",
        "node_attestation": {
            "node_id": "node-01",
            "environment_class": "NON_PRODUCTION_VPS",
            "operator_confirmed": True,
            "uid": 1001,
            "hostname_hash": "sha256:" + "1" * 64,
            "boot_id_hash": "sha256:" + "2" * 64,
            "collector_version": "1.0",
            "repo_sha": "a" * 40,
            "observed_at_epoch": NOW,
        },
        "checks": [
            {
                "name": name,
                "result": "PASS",
                "source_reference": f"vps:node-01:{name}",
                "observed_at_epoch": NOW,
            }
            for name in CONTRACT["required_checks"]
        ],
    }


def test_cli_writes_ready_resolution_for_valid_live_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        evidence_path = Path(tmp) / "evidence.json"
        output_path = Path(tmp) / "resolution.json"
        evidence_path.write_text(json.dumps(live_evidence()), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(HERE / "resolve_live_canary.py"),
                "--contract",
                str(HERE / "vps-canary-contract.json"),
                "--evidence",
                str(evidence_path),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        resolution = json.loads(output_path.read_text(encoding="utf-8"))
        assert proc.returncode == 0
        assert resolution["status"] == "PASS"
        assert resolution["live_vps_verified"] is True
        assert resolution["activation_status"] == "READY"


def test_cli_returns_nonzero_for_synthetic_fixture():
    with tempfile.TemporaryDirectory() as tmp:
        evidence_path = Path(tmp) / "evidence.json"
        output_path = Path(tmp) / "resolution.json"
        evidence = live_evidence()
        evidence["evidence_class"] = "SYNTHETIC_VALIDATOR_FIXTURE"
        evidence.pop("node_attestation")
        for row in evidence["checks"]:
            row["source_reference"] = f"synthetic:{row['name']}"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(HERE / "resolve_live_canary.py"),
                "--contract",
                str(HERE / "vps-canary-contract.json"),
                "--evidence",
                str(evidence_path),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        resolution = json.loads(output_path.read_text(encoding="utf-8"))
        assert proc.returncode == 1
        assert resolution["status"] == "PASS"
        assert resolution["live_vps_verified"] is False
        assert resolution["activation_status"] == "HOLD"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} LOM VPS live-canary resolver CLI tests")
