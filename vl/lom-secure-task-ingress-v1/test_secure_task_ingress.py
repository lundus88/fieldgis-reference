from datetime import datetime, timedelta, timezone

from secure_task_ingress import SCHEMA, SecureTaskIngress, sign_task

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
SECRET = b"test-only-secret-never-production"
PROJECT = "lom-vps-validation"


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
        "grant": {
            "capabilities": ["factory.plan"],
            "delegated_capabilities": ["factory.plan"],
            "scope": {"project_id": PROJECT, "target_environment": "staging"},
            "budget": {"timeout_seconds": 60, "max_retries": 0, "max_cost_minor": 0},
        },
        "evidence_refs": evidence,
    }
    env.update(overrides)
    return env


def submit(ingress, env):
    return ingress.submit(env, sign_task(env, SECRET), now=NOW)


def test_valid_task_is_buffered_not_executed():
    ingress = SecureTaskIngress(secret=SECRET, max_queue=4)
    result = submit(ingress, base_envelope())
    assert result["decision"] == "ACCEPTED"
    assert result["execution_performed"] is False
    assert result["production_locked"] is True
    assert ingress.status()["queue_depth"] == 1


def test_invalid_signature_fails_closed():
    ingress = SecureTaskIngress(secret=SECRET)
    result = ingress.submit(base_envelope(), "hmac-sha256:" + "0" * 64, now=NOW)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "SIGNATURE_INVALID"


def test_production_request_is_denied():
    ingress = SecureTaskIngress(secret=SECRET)
    env = base_envelope()
    env["body_request"] = dict(env["body_request"], production=True)
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "PRODUCTION_BOUNDARY_INVALID"


def test_connector_or_production_capability_is_denied():
    ingress = SecureTaskIngress(secret=SECRET)
    env = base_envelope()
    env["grant"] = dict(env["grant"], capabilities=["factory.plan", "connector.invoke:openclaw"])
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "FORBIDDEN_CAPABILITY_PRESENT"


def test_expired_task_is_denied():
    ingress = SecureTaskIngress(secret=SECRET)
    env = base_envelope(
        issued_at=(NOW - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        expires_at=(NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )
    result = submit(ingress, env)
    assert result["decision"] == "HOLD"


def test_identical_replay_is_idempotent():
    ingress = SecureTaskIngress(secret=SECRET)
    env = base_envelope()
    assert submit(ingress, env)["decision"] == "ACCEPTED"
    second = submit(ingress, env)
    assert second["decision"] == "ACCEPTED_IDEMPOTENT"
    assert ingress.status()["queue_depth"] == 1


def test_changed_replay_is_denied():
    ingress = SecureTaskIngress(secret=SECRET)
    env = base_envelope()
    assert submit(ingress, env)["decision"] == "ACCEPTED"
    changed = base_envelope(priority=81)
    result = submit(ingress, changed)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "TASK_ID_REPLAY_MISMATCH"


def test_queue_bound_is_enforced():
    ingress = SecureTaskIngress(secret=SECRET, max_queue=1)
    first = base_envelope()
    second = base_envelope(task_id="task-000000000002")
    assert submit(ingress, first)["decision"] == "ACCEPTED"
    result = submit(ingress, second)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "QUEUE_CAPACITY_REACHED"


def test_claim_releases_only_buffered_envelope():
    ingress = SecureTaskIngress(secret=SECRET)
    env = base_envelope()
    submit(ingress, env)
    claim = ingress.claim_next()
    assert claim["decision"] == "CLAIMED"
    assert claim["envelope"]["body_request"]["requested_action"] == "PREPARE_RUNTIME_DIAGNOSTIC_PR"
    assert claim["production_locked"] is True


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} Secure Task Ingress v1 tests")
