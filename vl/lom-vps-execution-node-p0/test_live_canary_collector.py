import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from collect_live_canary import collect_live_canary

NOW = 1_800_000_000
SHA = "a" * 40


def test_collector_requires_explicit_live_operator_confirmation():
    try:
        collect_live_canary(
            node_id="node-01",
            repo_sha=SHA,
            heartbeat_path=Path("/tmp/not-used"),
            operator_confirmed=False,
            observed_at_epoch=NOW,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "EXPLICIT_LIVE_VPS_CONFIRMATION_REQUIRED"


def test_collector_rejects_invalid_identity_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        for node, sha, reason in (
            ("bad node", SHA, "NODE_ID_INVALID"),
            ("node-01", "bad", "REPO_SHA_INVALID"),
        ):
            try:
                collect_live_canary(
                    node_id=node,
                    repo_sha=sha,
                    heartbeat_path=Path(tmp) / "heartbeat.json",
                    operator_confirmed=True,
                    observed_at_epoch=NOW,
                )
                assert False
            except ValueError as exc:
                assert str(exc) == reason


def test_collector_emits_live_attestation_and_all_required_named_checks():
    with tempfile.TemporaryDirectory() as tmp:
        heartbeat = Path(tmp) / "heartbeat.json"
        with patch("collect_live_canary._check_identity") as identity,              patch("collect_live_canary._check_sudo") as sudo,              patch("collect_live_canary._check_docker") as docker,              patch("collect_live_canary._check_secrets") as secrets,              patch("collect_live_canary._run_node_checks") as node_checks:
            identity.return_value = {"name": "unprivileged_os_identity", "result": "PASS", "source_reference": "vps:node-01:a", "observed_at_epoch": NOW}
            sudo.return_value = {"name": "sudo_denied", "result": "PASS", "source_reference": "vps:node-01:b", "observed_at_epoch": NOW}
            docker.return_value = {"name": "docker_socket_denied", "result": "PASS", "source_reference": "vps:node-01:c", "observed_at_epoch": NOW}
            secrets.return_value = {"name": "production_secrets_absent", "result": "PASS", "source_reference": "vps:node-01:d", "observed_at_epoch": NOW}
            node_checks.return_value = [
                {"name": name, "result": "PASS", "source_reference": f"vps:node-01:{name}", "observed_at_epoch": NOW}
                for name in (
                    "acp_allow_enforced",
                    "registered_health_probe_pass",
                    "acp_deny_enforced",
                    "production_capability_denied",
                    "connector_capability_denied",
                    "identical_replay_idempotent",
                    "changed_replay_denied",
                    "journal_restart_integrity",
                )
            ]
            evidence = collect_live_canary(
                node_id="node-01",
                repo_sha=SHA,
                heartbeat_path=heartbeat,
                operator_confirmed=True,
                observed_at_epoch=NOW,
            )

    assert evidence["evidence_class"] == "LIVE_VPS_CANARY"
    assert evidence["node_attestation"]["environment_class"] == "NON_PRODUCTION_VPS"
    assert evidence["node_attestation"]["operator_confirmed"] is True
    assert evidence["node_attestation"]["repo_sha"] == SHA
    assert len(evidence["checks"]) == 13
    assert all(row["source_reference"].startswith("vps:node-01:") for row in evidence["checks"])


def test_live_collector_never_records_secret_values():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "super-secret-value"}, clear=False):
        from collect_live_canary import _check_secrets
        row = _check_secrets("node-01", NOW)
    raw = str(row)
    assert row["result"] == "FAIL"
    assert "OPENAI_API_KEY" in raw
    assert "super-secret-value" not in raw


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} LOM VPS live-canary collector tests")
