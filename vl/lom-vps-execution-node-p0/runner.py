from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

NODE_SCHEMA = "lom.vps-execution-node/1"
RESULT_SCHEMA = "lom.vps-execution-result/1"
JOURNAL_SCHEMA = "lom.vps-execution-journal/1"

ALLOWED_CAPABILITIES = {
    "spec.read",
    "artifact.read",
    "qa.execute",
    "factory.plan",
    "certification.propose",
    "release.request_approval",
}

TASK_CAPABILITY = {
    "health_probe": "qa.execute",
    "run_registered_test": "qa.execute",
    "read_artifact_metadata": "artifact.read",
    "prepare_factory_plan": "factory.plan",
    "prepare_certification": "certification.propose",
    "prepare_release_request": "release.request_approval",
}

FORBIDDEN_CAPABILITY_PREFIXES = ("production.", "connector.invoke:")
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
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _load_acp_runtime():
    path = ROOT / "agent-control-plane" / "runtime_policy.py"
    spec = importlib.util.spec_from_file_location("lom_vps_acp_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ACP_RUNTIME_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class NodeTask:
    task_type: str
    payload: dict[str, Any]


class ExecutionJournal:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def verify(self) -> dict[str, Any]:
        rows = self._read()
        previous = "GENESIS"
        for expected, row in enumerate(rows, start=1):
            if row.get("schema") != JOURNAL_SCHEMA:
                return {"status": "HOLD", "reason": "JOURNAL_SCHEMA_MISMATCH"}
            if row.get("sequence") != expected or row.get("previous_digest") != previous:
                return {"status": "HOLD", "reason": "JOURNAL_CHAIN_MISMATCH"}
            body = dict(row)
            stored = body.pop("record_digest", None)
            if stored != _digest(body):
                return {"status": "HOLD", "reason": "JOURNAL_DIGEST_MISMATCH"}
            previous = stored
        return {"status": "READY", "count": len(rows), "tail": previous}

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        check = self.verify()
        if check["status"] != "READY":
            raise ValueError(check["reason"])
        body = {
            "schema": JOURNAL_SCHEMA,
            "sequence": check["count"] + 1,
            "previous_digest": check["tail"],
            **record,
        }
        body["record_digest"] = _digest(body)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return body


def validate_node_environment(env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env if env is not None else dict(os.environ)
    leaked = sorted(key for key in FORBIDDEN_ENV_KEYS if env.get(key))
    if leaked:
        return {"status": "HOLD", "reason": "FORBIDDEN_SECRET_PRESENT", "keys": leaked}
    if env.get("DOCKER_HOST"):
        return {"status": "HOLD", "reason": "DOCKER_SOCKET_OR_REMOTE_HOST_FORBIDDEN"}
    return {"status": "READY", "reason": "LEAST_PRIVILEGE_ENVIRONMENT"}


def validate_task(task: NodeTask, capability: str) -> dict[str, Any]:
    expected = TASK_CAPABILITY.get(task.task_type)
    if expected is None:
        return {"status": "HOLD", "reason": "UNKNOWN_TASK_TYPE"}
    if capability != expected:
        return {"status": "HOLD", "reason": "TASK_CAPABILITY_MISMATCH"}
    if capability not in ALLOWED_CAPABILITIES or capability.startswith(FORBIDDEN_CAPABILITY_PREFIXES):
        return {"status": "HOLD", "reason": "NODE_CAPABILITY_FORBIDDEN"}

    payload = task.payload
    if not isinstance(payload, dict):
        return {"status": "HOLD", "reason": "TASK_PAYLOAD_REQUIRED"}
    forbidden = {"command", "shell", "url", "token", "secret", "credential", "script"}
    if forbidden.intersection(payload):
        return {"status": "HOLD", "reason": "ARBITRARY_EXECUTION_PRIMITIVE_FORBIDDEN"}

    if task.task_type == "run_registered_test":
        name = str(payload.get("test_name") or "")
        if not re.fullmatch(r"[a-z0-9._-]{1,80}", name):
            return {"status": "HOLD", "reason": "REGISTERED_TEST_NAME_REQUIRED"}
    if task.task_type == "read_artifact_metadata":
        artifact_id = str(payload.get("artifact_id") or "")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", artifact_id):
            return {"status": "HOLD", "reason": "ARTIFACT_ID_REQUIRED"}

    return {"status": "READY", "reason": "TASK_VALID"}


def _default_handlers() -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    return {
        "health_probe": lambda payload: {
            "probe": str(payload.get("probe") or "node"),
            "status": "PASS",
        },
        "run_registered_test": lambda payload: {
            "test_name": payload["test_name"],
            "status": "PASS",
            "mode": "REGISTERED_TEST_ONLY",
        },
        "read_artifact_metadata": lambda payload: {
            "artifact_id": payload["artifact_id"],
            "status": "READ_ONLY_METADATA",
        },
        "prepare_factory_plan": lambda payload: {
            "status": "PREPARED",
            "plan_digest": _digest(payload),
        },
        "prepare_certification": lambda payload: {
            "status": "PREPARED",
            "certification_digest": _digest(payload),
        },
        "prepare_release_request": lambda payload: {
            "status": "PREPARED",
            "release_execution": "DISABLED",
            "request_digest": _digest(payload),
        },
    }


def execute_node_action(
    *,
    action: dict[str, Any],
    grant: dict[str, Any],
    task: NodeTask,
    journal: ExecutionJournal,
    observed_at_epoch: int,
    replay_record: dict[str, str] | None = None,
    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    environment_check = validate_node_environment(environment)
    if environment_check["status"] != "READY":
        return _hold(action, environment_check["reason"], observed_at_epoch)

    capability = str(action.get("capability") or "")
    if capability.startswith(FORBIDDEN_CAPABILITY_PREFIXES) or capability not in ALLOWED_CAPABILITIES:
        return _hold(action, "NODE_CAPABILITY_FORBIDDEN", observed_at_epoch)

    scope = action.get("scope") or {}
    if scope.get("target_environment") not in {"development", "staging"}:
        return _hold(action, "NON_PRODUCTION_SCOPE_REQUIRED", observed_at_epoch)

    task_check = validate_task(task, capability)
    if task_check["status"] != "READY":
        return _hold(action, task_check["reason"], observed_at_epoch)

    acp = _load_acp_runtime()
    decision = acp.evaluate_runtime(
        action,
        grant,
        replay_record=replay_record,
        policy_available=True,
    )
    if decision.get("decision") != "allow":
        return _hold(action, decision.get("reason_code", "ACP_DENIED"), observed_at_epoch, decision=decision)

    if decision.get("replayed") is True:
        replay_evidence = _digest({
            "action_id": action.get("action_id"),
            "input_digest": action.get("input_digest"),
            "replay_record": (replay_record or {}).get(str(action.get("action_id") or "")),
        })
        return {
            "schema": RESULT_SCHEMA,
            "action_id": action.get("action_id"),
            "status": "IDEMPOTENT_NOOP",
            "reason": "ACP_IDENTICAL_REPLAY",
            "execution_performed": False,
            "evidence_id": replay_evidence,
            "production": False,
            "production_locked": True,
            "observed_at_epoch": observed_at_epoch,
            "autonomous_ceiling": "PREPARE_PR",
            "production_authority": "HUMAN_ONLY",
        }

    journal_check = journal.verify()
    if journal_check["status"] != "READY":
        return _hold(action, journal_check["reason"], observed_at_epoch)

    selected_handlers = handlers or _default_handlers()
    handler = selected_handlers.get(task.task_type)
    if handler is None:
        return _hold(action, "TASK_HANDLER_NOT_REGISTERED", observed_at_epoch)

    result = handler(task.payload)
    result_digest = _digest(result)
    action_id = str(action.get("action_id") or "")
    input_digest = str(action.get("input_digest") or "")

    journal_record = journal.append({
        "record_type": "EXECUTION_COMPLETED",
        "action_id": action_id,
        "capability": capability,
        "task_type": task.task_type,
        "input_digest": input_digest,
        "result_digest": result_digest,
        "observed_at_epoch": observed_at_epoch,
        "target_environment": scope.get("target_environment"),
        "production": False,
    })

    return {
        "schema": RESULT_SCHEMA,
        "action_id": action_id,
        "status": "SUCCEEDED",
        "reason": "BOUNDED_NONPRODUCTION_EXECUTION",
        "result": result,
        "result_digest": result_digest,
        "journal_record_digest": journal_record["record_digest"],
        "action_digest": journal_record["record_digest"],
        "execution_performed": True,
        "production": False,
        "production_locked": True,
        "observed_at_epoch": observed_at_epoch,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "connector_execution": "DISABLED",
        "arbitrary_shell": "DISABLED",
    }


def _hold(
    action: dict[str, Any],
    reason: str,
    observed_at_epoch: int,
    *,
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "action_id": action.get("action_id"),
        "status": "HOLD",
        "reason": reason,
        "policy_decision": decision,
        "execution_performed": False,
        "production": False,
        "production_locked": True,
        "observed_at_epoch": observed_at_epoch,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "connector_execution": "DISABLED",
        "arbitrary_shell": "DISABLED",
    }


def node_manifest() -> dict[str, Any]:
    body = {
        "schema": NODE_SCHEMA,
        "mode": "NON_PRODUCTION_PERSISTENT_WORKER_CANDIDATE",
        "allowed_capabilities": sorted(ALLOWED_CAPABILITIES),
        "task_capability_map": dict(sorted(TASK_CAPABILITY.items())),
        "target_environments": ["development", "staging"],
        "connector_execution": "DISABLED",
        "arbitrary_shell": "DISABLED",
        "docker_socket": "FORBIDDEN",
        "root_required": False,
        "production_credentials": "FORBIDDEN",
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }
    return {**body, "manifest_digest": _digest(body)}
