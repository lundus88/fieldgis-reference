import os
import tempfile
from datetime import datetime, timezone

from runner import (
    ExecutionJournal,
    NodeTask,
    execute_node_action,
    node_manifest,
    validate_node_environment,
)

NOW = 2_000_000_000
ACTION_ID = "lom-vps-action-00000001"
INPUT_DIGEST = "sha256:" + "a" * 64
PROJECT_ID = "11111111-1111-4111-8111-111111111111"


def action(capability="qa.execute", env="staging", **overrides):
    data = {
        "schema_version": "1.0",
        "action_id": ACTION_ID,
        "requested_at": "2033-05-18T03:31:00Z",
        "expires_at": "2033-05-18T04:31:00Z",
        "requester": {
            "agent_id": "lom-vps-runner",
            "agent_version": "p0",
            "role": "executor",
            "principal_type": "agent",
        },
        "capability": capability,
        "scope": {
            "project_id": PROJECT_ID,
            "target_environment": env,
        },
        "provenance": {
            "source_type": "workflow",
            "source_id": "github-run:1",
        },
        "input_digest": INPUT_DIGEST,
        "budget": {
            "timeout_seconds": 60,
            "max_retries": 0,
            "max_cost_minor": 0,
        },
    }
    data.update(overrides)
    return data


def grant(capability="qa.execute", env="staging"):
    return {
        "capabilities": [capability],
        "delegated_capabilities": [capability],
        "scope": {
            "project_id": PROJECT_ID,
            "target_environment": env,
        },
        "budget": {
            "timeout_seconds": 60,
            "max_retries": 0,
            "max_cost_minor": 0,
        },
    }


def run(tmp, **kwargs):
    return execute_node_action(
        action=kwargs.pop("action_value", action()),
        grant=kwargs.pop("grant_value", grant()),
        task=kwargs.pop("task", NodeTask("run_registered_test", {"test_name": "smoke"})),
        journal=ExecutionJournal(tmp),
        observed_at_epoch=NOW,
        environment={},
        **kwargs,
    )


def test_manifest_has_hard_boundaries():
    m = node_manifest()
    assert m["connector_execution"] == "DISABLED"
    assert m["arbitrary_shell"] == "DISABLED"
    assert m["docker_socket"] == "FORBIDDEN"
    assert m["production_authority"] == "HUMAN_ONLY"
    assert "production.approve" not in m["allowed_capabilities"]


def test_least_privilege_environment_rejects_secrets_and_docker_host():
    assert validate_node_environment({})["status"] == "READY"
    assert validate_node_environment({"OPENAI_API_KEY": "x"})["reason"] == "FORBIDDEN_SECRET_PRESENT"
    assert validate_node_environment({"DOCKER_HOST": "unix:///var/run/docker.sock"})["reason"] == "DOCKER_SOCKET_OR_REMOTE_HOST_FORBIDDEN"


def test_bounded_registered_test_executes_after_acp_allow():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        result = run(path)
        assert result["status"] == "SUCCEEDED"
        assert result["execution_performed"] is True
        assert result["result"]["test_name"] == "smoke"
        assert ExecutionJournal(path).verify()["status"] == "READY"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_production_scope_is_refused_before_execution():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        result = run(
            path,
            action_value=action(env="production"),
            grant_value=grant(env="production"),
        )
        assert result["status"] == "HOLD"
        assert result["reason"] == "NON_PRODUCTION_SCOPE_REQUIRED"
        assert result["execution_performed"] is False
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_connector_and_production_capabilities_are_forbidden():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        for capability in ("connector.invoke:openclaw", "production.promote", "production.approve"):
            result = run(
                path,
                action_value=action(capability=capability),
                grant_value=grant(capability=capability),
                task=NodeTask("health_probe", {"probe": "node"}),
            )
            assert result["status"] == "HOLD"
            assert result["reason"] == "NODE_CAPABILITY_FORBIDDEN"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_arbitrary_shell_url_and_secret_payloads_are_forbidden():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        for payload in (
            {"test_name": "smoke", "command": "rm -rf /"},
            {"test_name": "smoke", "url": "https://example.com"},
            {"test_name": "smoke", "secret": "x"},
        ):
            result = run(path, task=NodeTask("run_registered_test", payload))
            assert result["status"] == "HOLD"
            assert result["reason"] == "ARBITRARY_EXECUTION_PRIMITIVE_FORBIDDEN"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_task_capability_mismatch_is_refused():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        result = run(
            path,
            action_value=action(capability="artifact.read"),
            grant_value=grant(capability="artifact.read"),
            task=NodeTask("run_registered_test", {"test_name": "smoke"}),
        )
        assert result["status"] == "HOLD"
        assert result["reason"] == "TASK_CAPABILITY_MISMATCH"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_acp_denial_is_preserved():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        result = run(
            path,
            grant_value=grant(capability="artifact.read"),
        )
        assert result["status"] == "HOLD"
        assert result["reason"] == "DENY_CAPABILITY_NOT_GRANTED"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_identical_replay_is_idempotent_noop():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        result = run(path, replay_record={ACTION_ID: INPUT_DIGEST})
        assert result["status"] == "IDEMPOTENT_NOOP"
        assert result["execution_performed"] is False
        assert not os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_changed_replay_is_denied():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        result = run(path, replay_record={ACTION_ID: "sha256:" + "b" * 64})
        assert result["status"] == "HOLD"
        assert result["reason"] == "DENY_REPLAY"
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_journal_tamper_is_detected():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.remove(path)
    try:
        first = run(path)
        assert first["status"] == "SUCCEEDED"
        text = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(text.replace("qa.execute", "artifact.read"))
        assert ExecutionJournal(path).verify()["status"] == "HOLD"
    finally:
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LOM VPS Execution Node P0 tests")
