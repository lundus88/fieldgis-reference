from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import grp
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
from typing import Any

from runner import ExecutionJournal, NodeTask, execute_node_action

COLLECTOR_VERSION = "1.0"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
NODE_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
FORBIDDEN_ENV_KEYS = {
    "SUPABASE_SERVICE_ROLE_KEY",
    "VERCEL_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "BILLPLZ_SECRET_KEY",
    "GITHUB_TOKEN",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
    "ACTIONS_ID_TOKEN_REQUEST_URL",
}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _hash_text(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _source(node_id: str, name: str, detail: dict[str, Any]) -> str:
    return f"vps:{node_id}:{name}:{_digest(detail).split(':', 1)[1][:16]}"


def _row(node_id: str, name: str, passed: bool, observed_at: int, detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "result": "PASS" if passed else "FAIL",
        "source_reference": _source(node_id, name, detail),
        "observed_at_epoch": observed_at,
        "detail": detail,
    }


def _safe_groups() -> list[str]:
    names: list[str] = []
    for gid in os.getgroups():
        try:
            names.append(grp.getgrgid(gid).gr_name)
        except KeyError:
            names.append(str(gid))
    return sorted(set(names))


def _check_identity(node_id: str, observed_at: int) -> dict[str, Any]:
    uid = os.geteuid()
    detail = {"uid": uid, "root": uid == 0}
    return _row(node_id, "unprivileged_os_identity", uid != 0, observed_at, detail)


def _check_sudo(node_id: str, observed_at: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["sudo", "-n", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        denied = proc.returncode != 0
        detail = {"sudo_present": True, "return_code": proc.returncode}
    except FileNotFoundError:
        denied = True
        detail = {"sudo_present": False, "return_code": None}
    except subprocess.TimeoutExpired:
        denied = True
        detail = {"sudo_present": True, "timed_out": True}
    return _row(node_id, "sudo_denied", denied, observed_at, detail)


def _check_docker(node_id: str, observed_at: int) -> dict[str, Any]:
    path = "/var/run/docker.sock"
    groups = _safe_groups()
    exists = os.path.exists(path)
    accessible = os.access(path, os.R_OK | os.W_OK) if exists else False
    in_docker_group = "docker" in groups
    detail = {
        "socket_exists": exists,
        "socket_read_write_access": accessible,
        "docker_group_member": in_docker_group,
    }
    return _row(
        node_id,
        "docker_socket_denied",
        not accessible and not in_docker_group,
        observed_at,
        detail,
    )


def _check_secrets(node_id: str, observed_at: int) -> dict[str, Any]:
    present = sorted(key for key in FORBIDDEN_ENV_KEYS if os.environ.get(key))
    detail = {"present_forbidden_key_names": present, "values_recorded": False}
    return _row(node_id, "production_secrets_absent", not present, observed_at, detail)


def _action(now: datetime, action_id: str, capability: str = "qa.execute") -> dict[str, Any]:
    payload = {"canary": True, "action_id": action_id, "capability": capability}
    return {
        "schema_version": "1.0",
        "action_id": action_id,
        "requested_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "requester": {
            "agent_id": "lom-vps-runner",
            "agent_version": "p1-live-canary",
            "role": "executor",
            "principal_type": "agent",
        },
        "capability": capability,
        "scope": {
            "project_id": "lom-vps-canary",
            "target_environment": "staging",
        },
        "provenance": {
            "source_type": "live_vps_canary",
            "source_id": action_id,
        },
        "input_digest": _digest(payload),
        "budget": {
            "timeout_seconds": 30,
            "max_retries": 0,
            "max_cost_minor": 0,
        },
    }


def _grant(capability: str = "qa.execute") -> dict[str, Any]:
    return {
        "capabilities": [capability],
        "delegated_capabilities": [capability],
        "scope": {
            "project_id": "lom-vps-canary",
            "target_environment": "staging",
        },
        "budget": {
            "timeout_seconds": 30,
            "max_retries": 0,
            "max_cost_minor": 0,
        },
    }


def _run_node_checks(node_id: str, observed_at: int) -> list[dict[str, Any]]:
    now = datetime.fromtimestamp(observed_at, tz=timezone.utc)
    rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="lom-vps-canary-") as tmp:
        journal_path = str(Path(tmp) / "journal.jsonl")
        journal = ExecutionJournal(journal_path)

        allow_action = _action(now, f"live-allow-{observed_at}")
        allow_result = execute_node_action(
            action=allow_action,
            grant=_grant("qa.execute"),
            task=NodeTask("health_probe", {"probe": "live-vps"}),
            journal=journal,
            observed_at_epoch=observed_at,
            environment={},
        )
        allow_ok = allow_result.get("status") == "SUCCEEDED" and allow_result.get("execution_performed") is True
        rows.append(_row(
            node_id,
            "acp_allow_enforced",
            allow_ok,
            observed_at,
            {"status": allow_result.get("status"), "reason": allow_result.get("reason")},
        ))
        rows.append(_row(
            node_id,
            "registered_health_probe_pass",
            allow_ok and (allow_result.get("result") or {}).get("status") == "PASS",
            observed_at,
            {"probe_result": (allow_result.get("result") or {}).get("status")},
        ))

        deny_action = _action(now, f"live-deny-{observed_at}")
        deny_result = execute_node_action(
            action=deny_action,
            grant=_grant("artifact.read"),
            task=NodeTask("health_probe", {"probe": "live-vps"}),
            journal=journal,
            observed_at_epoch=observed_at,
            environment={},
        )
        rows.append(_row(
            node_id,
            "acp_deny_enforced",
            deny_result.get("status") == "HOLD" and deny_result.get("execution_performed") is False,
            observed_at,
            {"status": deny_result.get("status"), "reason": deny_result.get("reason")},
        ))

        prod_action = _action(now, f"live-prod-{observed_at}", "production.promote")
        prod_result = execute_node_action(
            action=prod_action,
            grant=_grant("production.promote"),
            task=NodeTask("health_probe", {"probe": "live-vps"}),
            journal=journal,
            observed_at_epoch=observed_at,
            environment={},
        )
        rows.append(_row(
            node_id,
            "production_capability_denied",
            prod_result.get("status") == "HOLD" and prod_result.get("execution_performed") is False,
            observed_at,
            {"status": prod_result.get("status"), "reason": prod_result.get("reason")},
        ))

        connector_action = _action(now, f"live-connector-{observed_at}", "connector.invoke:openclaw")
        connector_result = execute_node_action(
            action=connector_action,
            grant=_grant("connector.invoke:openclaw"),
            task=NodeTask("health_probe", {"probe": "live-vps"}),
            journal=journal,
            observed_at_epoch=observed_at,
            environment={},
        )
        rows.append(_row(
            node_id,
            "connector_capability_denied",
            connector_result.get("status") == "HOLD" and connector_result.get("execution_performed") is False,
            observed_at,
            {"status": connector_result.get("status"), "reason": connector_result.get("reason")},
        ))

        replay_action = _action(now, f"live-replay-{observed_at}")
        replay = {replay_action["action_id"]: replay_action["input_digest"]}
        replay_result = execute_node_action(
            action=replay_action,
            grant=_grant("qa.execute"),
            task=NodeTask("health_probe", {"probe": "live-vps"}),
            journal=journal,
            observed_at_epoch=observed_at,
            replay_record=replay,
            environment={},
        )
        rows.append(_row(
            node_id,
            "identical_replay_idempotent",
            replay_result.get("status") == "IDEMPOTENT_NOOP" and replay_result.get("execution_performed") is False,
            observed_at,
            {"status": replay_result.get("status"), "reason": replay_result.get("reason")},
        ))

        changed = {replay_action["action_id"]: "sha256:" + "0" * 64}
        changed_result = execute_node_action(
            action=replay_action,
            grant=_grant("qa.execute"),
            task=NodeTask("health_probe", {"probe": "live-vps"}),
            journal=journal,
            observed_at_epoch=observed_at,
            replay_record=changed,
            environment={},
        )
        rows.append(_row(
            node_id,
            "changed_replay_denied",
            changed_result.get("status") == "HOLD" and changed_result.get("execution_performed") is False,
            observed_at,
            {"status": changed_result.get("status"), "reason": changed_result.get("reason")},
        ))

        reopened = ExecutionJournal(journal_path).verify()
        rows.append(_row(
            node_id,
            "journal_restart_integrity",
            reopened.get("status") == "READY" and reopened.get("count", 0) >= 1,
            observed_at,
            {"status": reopened.get("status"), "count": reopened.get("count")},
        ))

    return rows


def _heartbeat(node_id: str, observed_at: int, heartbeat_path: Path) -> dict[str, Any]:
    body = {
        "schema": "lom.vps-heartbeat/1",
        "node_id": node_id,
        "observed_at_epoch": observed_at,
        "status": "ALIVE",
    }
    body["heartbeat_digest"] = _digest(body)
    try:
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        with heartbeat_path.open("w", encoding="utf-8") as handle:
            json.dump(body, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        loaded = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        valid = loaded.get("heartbeat_digest") == body["heartbeat_digest"]
        detail = {
            "path_hash": _hash_text(str(heartbeat_path)),
            "heartbeat_digest": body["heartbeat_digest"],
            "reread_valid": valid,
        }
    except OSError as exc:
        valid = False
        detail = {"error_type": type(exc).__name__, "path_value_recorded": False}
    return _row(node_id, "heartbeat_evidence_available", valid, observed_at, detail)


def collect_live_canary(
    *,
    node_id: str,
    repo_sha: str,
    heartbeat_path: Path,
    operator_confirmed: bool,
    observed_at_epoch: int | None = None,
) -> dict[str, Any]:
    if not operator_confirmed:
        raise ValueError("EXPLICIT_LIVE_VPS_CONFIRMATION_REQUIRED")
    if not NODE_RE.fullmatch(node_id):
        raise ValueError("NODE_ID_INVALID")
    if not SHA_RE.fullmatch(repo_sha):
        raise ValueError("REPO_SHA_INVALID")

    observed_at = observed_at_epoch or int(datetime.now(timezone.utc).timestamp())
    hostname = socket.gethostname()
    boot_id_path = Path("/proc/sys/kernel/random/boot_id")
    try:
        boot_id = boot_id_path.read_text(encoding="utf-8").strip()
    except OSError:
        boot_id = "unavailable"

    rows = [
        _check_identity(node_id, observed_at),
        _check_sudo(node_id, observed_at),
        _check_docker(node_id, observed_at),
        _check_secrets(node_id, observed_at),
    ]
    rows.extend(_run_node_checks(node_id, observed_at))
    rows.append(_heartbeat(node_id, observed_at, heartbeat_path))

    return {
        "schema": "lom.vps-canary-evidence/1",
        "evidence_class": "LIVE_VPS_CANARY",
        "node_attestation": {
            "node_id": node_id,
            "environment_class": "NON_PRODUCTION_VPS",
            "operator_confirmed": True,
            "uid": os.geteuid(),
            "hostname_hash": _hash_text(hostname),
            "boot_id_hash": _hash_text(boot_id),
            "collector_version": COLLECTOR_VERSION,
            "repo_sha": repo_sha,
            "observed_at_epoch": observed_at,
        },
        "checks": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect machine-readable LOM VPS live-canary evidence.")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--repo-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--heartbeat-path",
        default=str(Path.home() / ".local/state/lom-vps/heartbeat.json"),
    )
    parser.add_argument(
        "--confirm-live-vps",
        action="store_true",
        help="Required explicit acknowledgement that this command is running on the authorized non-Production VPS.",
    )
    args = parser.parse_args()

    try:
        evidence = collect_live_canary(
            node_id=args.node_id,
            repo_sha=args.repo_sha,
            heartbeat_path=Path(args.heartbeat_path),
            operator_confirmed=args.confirm_live_vps,
        )
    except ValueError as exc:
        print(str(exc))
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "COLLECTED",
        "output": str(output),
        "checks": len(evidence["checks"]),
        "failed": [row["name"] for row in evidence["checks"] if row["result"] != "PASS"],
        "observed_at": _iso(evidence["node_attestation"]["observed_at_epoch"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
