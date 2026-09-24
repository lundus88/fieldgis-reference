from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from secure_task_ingress import SCHEMA, SecureTaskIngress, sign_task

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
SECRET = b"test-only-secret-never-production"
KEY_ID = "test-key-v1"
PROJECT = "lom-vps-validation"


def new_ingress(**overrides):
    tempdir = TemporaryDirectory()
    instance = SecureTaskIngress(
        store_path=Path(tempdir.name) / "ingress.db",
        signing_keys={KEY_ID: SECRET},
        **overrides,
    )
    instance._test_tempdir = tempdir
    return instance


def base_envelope(**overrides):
    idem = "sha256:" + "2" * 64
    evidence = ["live-vps-canary:13-of-13"]
    body = {
        "schema": "lom.organism-bounded-delegation/1",
        "signal_id": "sig-ingress-1",
        "project_id": PROJECT,
        "route_digest": "sha256:" + "1" * 64,
        "requested_action": "PREPARE_RUNTIME_DIAGNOSTIC_PR",
        "steps": ["VERIFY_EVIDENCE", "PREPARE_BOUNDED_CANDIDATE"],
        "max_authority": "PREPARE_PR",
        "production": False,
        "production_locked": True,
        "idempotency_key": idem,
        "evidence_refs": evidence,
    }
    env = {
        "schema": SCHEMA,
        "task_id": "task-000000000001",
        "issued_at": (NOW - timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "tenant": "lom",
        "priority": 80,
        "idempotency_key": idem,
        "body_request": body,
        "grant_ref": "acp-grant:test-grant-0001",
        "target_environment": "staging",
        "evidence_refs": evidence,
        "signing_key_id": KEY_ID,
    }
    env.update(overrides)
    return env


def submit(ingress, env):
    return ingress.submit(env, sign_task(env, SECRET), now=NOW)


def test_valid_task_is_buffered_not_executed():
    ingress = new_ingress(max_queue=4)
    result = submit(ingress, base_envelope())
    assert result["decision"] == "ACCEPTED"
    assert result["execution_performed"] is False
    assert result["production_locked"] is True
    assert ingress.status()["queue_depth"] == 1
    ingress.close()


def test_invalid_signature_fails_closed():
    ingress = new_ingress()
    result = ingress.submit(base_envelope(), "hmac-sha256:" + "0" * 64, now=NOW)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "SIGNATURE_INVALID"
    ingress.close()


def test_production_request_is_denied():
    ingress = new_ingress()
    env = base_envelope()
    env["body_request"] = dict(env["body_request"], production=True)
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "PRODUCTION_BOUNDARY_INVALID"
    ingress.close()


def test_caller_supplied_grant_is_rejected():
    ingress = new_ingress()
    env = base_envelope()
    env["grant"] = {
        "capabilities": ["factory.plan"],
        "scope": {"project_id": PROJECT, "target_environment": "staging"},
    }
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "ENVELOPE_FIELDS_INVALID"
    ingress.close()


def test_connector_action_is_denied():
    ingress = new_ingress()
    env = base_envelope()
    env["body_request"] = dict(
        env["body_request"], requested_action="connector.invoke:openclaw"
    )
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "BODY_ACTION_NOT_REGISTERED"
    ingress.close()


def test_arbitrary_shell_primitive_is_denied():
    ingress = new_ingress()
    env = base_envelope()
    env["body_request"] = dict(
        env["body_request"], steps=[{"command": "echo forbidden"}]
    )
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "ARBITRARY_EXECUTION_PRIMITIVE_FORBIDDEN"
    ingress.close()


def test_expired_task_is_denied():
    ingress = new_ingress()
    env = base_envelope(
        issued_at=(NOW - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        expires_at=(NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"
    ingress.close()


def test_identical_replay_is_idempotent():
    ingress = new_ingress()
    env = base_envelope()
    assert submit(ingress, env)["decision"] == "ACCEPTED"
    second = submit(ingress, env)
    assert second["decision"] == "ACCEPTED_IDEMPOTENT"
    assert ingress.status()["queue_depth"] == 1
    ingress.close()


def test_changed_replay_is_denied():
    ingress = new_ingress()
    env = base_envelope()
    assert submit(ingress, env)["decision"] == "ACCEPTED"
    changed = base_envelope(priority=81)
    result = submit(ingress, changed)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "TASK_ID_REPLAY_MISMATCH"
    ingress.close()


def test_queue_bound_is_enforced():
    ingress = new_ingress(max_queue=1)
    first = base_envelope()
    second = base_envelope(task_id="task-000000000002")
    assert submit(ingress, first)["decision"] == "ACCEPTED"
    result = submit(ingress, second)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "QUEUE_CAPACITY_REACHED"
    ingress.close()


def test_claim_releases_only_buffered_envelope():
    ingress = new_ingress()
    env = base_envelope()
    submit(ingress, env)
    claim = ingress.claim_next(owner_id="lom-worker-test", now=NOW)
    assert claim["decision"] == "CLAIMED"
    assert claim["envelope"]["body_request"]["requested_action"] == "PREPARE_RUNTIME_DIAGNOSTIC_PR"
    assert claim["envelope"]["grant_ref"] == "acp-grant:test-grant-0001"
    assert "grant" not in claim["envelope"]
    assert claim["production_locked"] is True
    ingress.close()


def test_audit_chain_remains_valid():
    ingress = new_ingress()
    assert submit(ingress, base_envelope())["decision"] == "ACCEPTED"
    status = ingress.status()
    assert status["audit_chain"]["status"] == "READY"
    assert status["caller_supplied_grant"] == "FORBIDDEN"
    assert status["connector_execution"] == "FORBIDDEN"
    assert status["autonomous_ceiling"] == "PREPARE_PR"
    ingress.close()


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} Secure Task Ingress v1 tests")
