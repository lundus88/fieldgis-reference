import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from body_executor_adapter import VPSBodyExecutorAdapter
from runner import ExecutionJournal

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "vps-canary-contract.json").read_text(encoding="utf-8"))
NOW = 2_000_000_000
PROJECT = "ebkl"


def canary(live=True, observed_at=NOW):
    out = {
        "schema": "lom.vps-canary-evidence/1",
        "evidence_class": "LIVE_VPS_CANARY" if live else "SYNTHETIC_VALIDATOR_FIXTURE",
        "checks": [
            {
                "name": name,
                "result": "PASS",
                "source_reference": (
                    f"vps:node-01:{name}" if live else f"synthetic:{name}"
                ),
                "observed_at_epoch": observed_at,
            }
            for name in CONTRACT["required_checks"]
        ],
    }
    if live:
        out["node_attestation"] = {
            "node_id": "node-01",
            "environment_class": "NON_PRODUCTION_VPS",
            "operator_confirmed": True,
            "uid": 1001,
            "hostname_hash": "sha256:" + "1" * 64,
            "boot_id_hash": "sha256:" + "2" * 64,
            "collector_version": "1.0",
            "repo_sha": "a" * 40,
            "observed_at_epoch": observed_at,
        }
    return out


def grant():
    return {
        "capabilities": ["factory.plan"],
        "delegated_capabilities": ["factory.plan"],
        "scope": {
            "project_id": PROJECT,
            "target_environment": "staging",
        },
        "budget": {
            "timeout_seconds": 60,
            "max_retries": 0,
            "max_cost_minor": 0,
        },
    }


def request(**overrides):
    data = {
        "schema": "lom.organism-bounded-delegation/1",
        "signal_id": "sig-1",
        "project_id": PROJECT,
        "route_digest": "sha256:" + "1" * 64,
        "requested_action": "PREPARE_CI_REMEDIATION_PR",
        "steps": ["VERIFY_EVIDENCE", "PREPARE_BOUNDED_CANDIDATE"],
        "max_authority": "PREPARE_PR",
        "production": False,
        "production_locked": True,
        "idempotency_key": "sha256:" + "2" * 64,
        "evidence_refs": ["health:assessment:1"],
    }
    data.update(overrides)
    return data


def clock():
    return datetime.fromtimestamp(NOW, tz=timezone.utc)


def make_adapter(path, **overrides):
    args = {
        "grant": grant(),
        "journal": ExecutionJournal(path),
        "canary_contract": CONTRACT,
        "canary_evidence": canary(),
        "target_environment": "staging",
        "max_canary_age_seconds": 900,
        "environment": {},
        "clock": clock,
    }
    args.update(overrides)
    return VPSBodyExecutorAdapter(**args)


def fresh_path():
    fd, path = tempfile.mkstemp(prefix="lom-vps-body-", suffix=".jsonl")
    os.close(fd)
    os.remove(path)
    return path


def test_live_canary_allows_bounded_body_preparation():
    path = fresh_path()
    try:
        adapter = make_adapter(path)
        result = adapter(request())
        assert result["decision"] == "ALLOW"
        assert result["reason"] == "VPS_BOUNDED_PREPARATION_VERIFIED"
        assert result["production_locked"] is True
        assert result["production"] is False
        assert result["action_digest"]
        assert ExecutionJournal(path).verify()["status"] == "READY"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_synthetic_canary_never_activates_body_executor():
    path = fresh_path()
    try:
        adapter = make_adapter(path, canary_evidence=canary(live=False))
        result = adapter(request())
        assert result["decision"] == "HOLD"
        assert result["reason"] == "LIVE_VPS_NOT_VERIFIED"
        assert not os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_stale_live_canary_holds():
    path = fresh_path()
    try:
        adapter = make_adapter(path, canary_evidence=canary(observed_at=NOW - 901))
        result = adapter(request())
        assert result["decision"] == "HOLD"
        assert result["reason"] == "LIVE_VPS_CANARY_STALE"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_production_boundary_cannot_be_widened_by_body_request():
    path = fresh_path()
    try:
        adapter = make_adapter(path)
        result = adapter(request(production=True))
        assert result["decision"] == "HOLD"
        assert result["reason"] == "BODY_PRODUCTION_BOUNDARY_INVALID"
        assert not os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_unknown_body_action_is_not_mapped_to_generic_execution():
    path = fresh_path()
    try:
        adapter = make_adapter(path)
        result = adapter(request(requested_action="RUN_ARBITRARY_COMMAND"))
        assert result["decision"] == "HOLD"
        assert result["reason"] == "BODY_ACTION_NOT_REGISTERED"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_identical_body_request_is_idempotent_with_evidence():
    path = fresh_path()
    try:
        replay = {}
        adapter = make_adapter(path, replay_record=replay)
        first = adapter(request())
        second = adapter(request())
        assert first["decision"] == "ALLOW"
        assert second["decision"] == "ALLOW"
        assert second["reason"] == "VPS_IDEMPOTENT_REPLAY"
        assert second["evidence_id"].startswith("sha256:")
        assert ExecutionJournal(path).verify()["count"] == 1
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_grant_scope_must_match_project():
    path = fresh_path()
    try:
        wrong = grant()
        wrong["scope"]["project_id"] = "other"
        adapter = make_adapter(path, grant=wrong)
        result = adapter(request())
        assert result["decision"] == "HOLD"
        assert result["reason"] == "GRANT_PROJECT_SCOPE_MISMATCH"
    finally:
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} LOM VPS BodyRuntime adapter tests")
