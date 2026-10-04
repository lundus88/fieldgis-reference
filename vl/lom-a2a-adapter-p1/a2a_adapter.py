from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

SCHEMA = "lom.a2a-adapter/1"
A2A_PROTOCOL_VERSION = "1.0"
A2A_RELEASE_BASELINE = "v1.0.0"

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"

ALLOWED_ACTION = "READ_ONLY_OBSERVATION"
ALLOWED_CAPABILITY = "cap.observe.readonly"
ALLOWED_BINDINGS = {"JSONRPC", "HTTP+JSON", "GRPC"}
TASK_STATES = {
    "TASK_STATE_SUBMITTED",
    "TASK_STATE_WORKING",
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_REJECTED",
    "TASK_STATE_AUTH_REQUIRED",
}
HUMAN_GATE_STATES = {"TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED"}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _hold(reason: str) -> dict[str, Any]:
    body = {
        "schema": SCHEMA,
        "status": "HOLD",
        "reason": reason,
        "eligible_skills": [],
        "denied_skills": [],
        "network_access": "DISABLED",
        "credential_access": "NONE",
        "live_message_send": "DISABLED",
        "live_stream": "DISABLED",
        "live_task_runtime": "DISABLED",
        "external_delegation": "DISABLED",
        "agent_authority_trusted": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
    }
    return {**body, "projection_digest": digest(body)}


def _connector_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if registry.get("schema") != "lom.connector-registry/1":
        raise ValueError("CONNECTOR_REGISTRY_SCHEMA_INVALID")
    if registry.get("default_decision") != "deny":
        raise ValueError("CONNECTOR_REGISTRY_DEFAULT_DENY_REQUIRED")
    if registry.get("production_locked") is not True:
        raise ValueError("CONNECTOR_REGISTRY_PRODUCTION_LOCK_REQUIRED")
    if registry.get("write_authority") is not False:
        raise ValueError("CONNECTOR_WRITE_AUTHORITY_FORBIDDEN")
    if registry.get("paid_action_authority") is not False:
        raise ValueError("CONNECTOR_PAID_AUTHORITY_FORBIDDEN")
    if registry.get("ambient_credentials_allowed") is not False:
        raise ValueError("AMBIENT_CREDENTIALS_FORBIDDEN")
    connectors = registry.get("connectors")
    if not isinstance(connectors, list) or not connectors:
        raise ValueError("CONNECTOR_REGISTRY_EMPTY")
    out: dict[str, dict[str, Any]] = {}
    for connector in connectors:
        if not isinstance(connector, dict):
            raise ValueError("CONNECTOR_RECORD_INVALID")
        cid = str(connector.get("id") or "").strip()
        if not cid or cid in out:
            raise ValueError("CONNECTOR_ID_INVALID")
        out[cid] = dict(connector)
    return out


def _action_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if registry.get("schema") != "lom.action-registry/1":
        raise ValueError("ACTION_REGISTRY_SCHEMA_INVALID")
    if registry.get("default_decision") != "DENY":
        raise ValueError("ACTION_REGISTRY_DEFAULT_DENY_REQUIRED")
    if registry.get("production_locked") is not True:
        raise ValueError("ACTION_REGISTRY_PRODUCTION_LOCK_REQUIRED")
    actions = registry.get("actions")
    if not isinstance(actions, list):
        raise ValueError("ACTION_REGISTRY_INVALID")
    out: dict[str, dict[str, Any]] = {}
    for action in actions:
        aid = str(action.get("action_id") or "").strip()
        if not aid or aid in out:
            raise ValueError("ACTION_ID_INVALID")
        out[aid] = dict(action)
    return out


def _validate_connector(connector: dict[str, Any]) -> None:
    if connector.get("status") != "certified-fixture":
        raise ValueError("A2A_CONNECTOR_NOT_CERTIFIED_FIXTURE")
    if connector.get("mode") != "read-only":
        raise ValueError("A2A_CONNECTOR_READ_ONLY_REQUIRED")
    if connector.get("allowed_operations") != ["read"]:
        raise ValueError("A2A_CONNECTOR_READ_ONLY_OPERATION_REQUIRED")
    if connector.get("external_runtime") is not False:
        raise ValueError("A2A_EXTERNAL_RUNTIME_FORBIDDEN_P1")
    if connector.get("credentials_required") is not False:
        raise ValueError("A2A_CREDENTIALS_FORBIDDEN_P1")
    if connector.get("protocol") != "a2a":
        raise ValueError("A2A_PROTOCOL_BINDING_REQUIRED")
    if connector.get("protocol_version") != A2A_PROTOCOL_VERSION:
        raise ValueError("A2A_PROTOCOL_VERSION_MISMATCH")
    if connector.get("network_access") != "DISABLED":
        raise ValueError("A2A_NETWORK_ACCESS_FORBIDDEN_P1")
    if connector.get("agent_authority_trusted") is not False:
        raise ValueError("A2A_AGENT_AUTHORITY_MUST_BE_UNTRUSTED")


def _local_bindings(
    rows: Iterable[dict[str, Any]],
    *,
    connector: dict[str, Any],
    actions: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    action = actions.get(ALLOWED_ACTION)
    if action is None:
        raise ValueError("A2A_LOCAL_ACTION_NOT_REGISTERED")
    if (
        action.get("capability_id") != ALLOWED_CAPABILITY
        or action.get("max_risk") != "LOW"
        or action.get("reversible_required") is not True
        or action.get("non_production_only") is not True
    ):
        raise ValueError("A2A_LOCAL_ACTION_CONTRACT_INVALID")

    scopes = set(str(x) for x in (connector.get("resource_scopes") or []))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("A2A_LOCAL_BINDING_INVALID")
        skill_id = str(row.get("a2a_skill_id") or "").strip()
        if not skill_id or skill_id in out:
            raise ValueError("A2A_LOCAL_BINDING_SKILL_INVALID")
        if row.get("connector_id") != connector.get("id"):
            raise ValueError("A2A_LOCAL_BINDING_CONNECTOR_MISMATCH")
        if row.get("action_id") != ALLOWED_ACTION:
            raise ValueError("A2A_LOCAL_BINDING_ACTION_FORBIDDEN")
        if row.get("capability_id") != ALLOWED_CAPABILITY:
            raise ValueError("A2A_LOCAL_BINDING_CAPABILITY_FORBIDDEN")
        scope = str(row.get("resource_scope") or "").strip()
        if scope not in scopes:
            raise ValueError("A2A_LOCAL_BINDING_SCOPE_MISMATCH")
        out[skill_id] = {
            "connector_id": connector["id"],
            "a2a_skill_id": skill_id,
            "action_id": ALLOWED_ACTION,
            "capability_id": ALLOWED_CAPABILITY,
            "resource_scope": scope,
            "risk": "LOW",
            "authority_source": "LOM_LOCAL_BINDING",
        }
    return out


def _interfaces(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("A2A_SUPPORTED_INTERFACES_REQUIRED")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("A2A_INTERFACE_INVALID")
        binding = str(row.get("protocolBinding") or "").strip()
        version = str(row.get("protocolVersion") or "").strip()
        url = str(row.get("url") or "").strip()
        if binding not in ALLOWED_BINDINGS:
            raise ValueError("A2A_PROTOCOL_BINDING_UNSUPPORTED")
        if version != A2A_PROTOCOL_VERSION:
            raise ValueError("A2A_INTERFACE_VERSION_MISMATCH")
        if not url:
            raise ValueError("A2A_INTERFACE_URL_REQUIRED")
        out.append({
            "protocol_binding": binding,
            "protocol_version": version,
            "url_present": True,
            "live_network_enabled": False,
        })
    return out


def _skill(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("A2A_SKILL_INVALID")
    skill_id = str(row.get("id") or "").strip()
    name = str(row.get("name") or "").strip()
    description = str(row.get("description") or "").strip()
    if not skill_id or not name or not description:
        raise ValueError("A2A_SKILL_IDENTITY_REQUIRED")
    tags = row.get("tags") or []
    if not isinstance(tags, list) or any(not str(x).strip() for x in tags):
        raise ValueError("A2A_SKILL_TAGS_INVALID")
    return {
        "id": skill_id,
        "name": name,
        "description": description,
        "tags": sorted(set(str(x).strip() for x in tags)),
        "examples_forwarded": False,
    }


def compile_agent_card_projection(
    *,
    connector_id: str,
    agent_card: dict[str, Any],
    connector_registry: dict[str, Any],
    action_registry: dict[str, Any],
    local_skill_bindings: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        connectors = _connector_index(connector_registry)
        actions = _action_index(action_registry)
        connector = connectors.get(connector_id)
        if connector is None:
            raise ValueError("A2A_CONNECTOR_NOT_REGISTERED")
        _validate_connector(connector)

        if not isinstance(agent_card, dict):
            raise ValueError("A2A_AGENT_CARD_INVALID")
        name = str(agent_card.get("name") or "").strip()
        description = str(agent_card.get("description") or "").strip()
        agent_version = str(agent_card.get("version") or "").strip()
        if not name or not description or not agent_version:
            raise ValueError("A2A_AGENT_IDENTITY_REQUIRED")

        interfaces = _interfaces(agent_card.get("supportedInterfaces"))
        caps = agent_card.get("capabilities")
        if not isinstance(caps, dict):
            raise ValueError("A2A_CAPABILITIES_INVALID")

        security_schemes = agent_card.get("securitySchemes") or {}
        security = agent_card.get("security") or []
        if security_schemes not in ({}, None) or security not in ([], None):
            raise ValueError("A2A_SECURITY_REQUIREMENTS_FORBIDDEN_P1")

        default_inputs = agent_card.get("defaultInputModes") or []
        default_outputs = agent_card.get("defaultOutputModes") or []
        if not isinstance(default_inputs, list) or not isinstance(default_outputs, list):
            raise ValueError("A2A_MEDIA_MODES_INVALID")

        raw_skills = agent_card.get("skills") or []
        if not isinstance(raw_skills, list) or not raw_skills:
            raise ValueError("A2A_SKILLS_REQUIRED")
        skills = [_skill(row) for row in raw_skills]
        ids = [row["id"] for row in skills]
        if len(ids) != len(set(ids)):
            raise ValueError("A2A_DUPLICATE_SKILL")

        bindings = _local_bindings(
            local_skill_bindings,
            connector=connector,
            actions=actions,
        )
        eligible = []
        denied = []
        for skill in sorted(skills, key=lambda x: x["id"]):
            binding = bindings.get(skill["id"])
            if binding is None:
                denied.append({
                    "id": skill["id"],
                    "name": skill["name"],
                    "decision": "HOLD",
                    "reason": "UNBOUND_A2A_SKILL",
                    "agent_claim_trusted_for_authority": False,
                })
            else:
                eligible.append({
                    **skill,
                    **binding,
                    "decision": "ALLOW_METADATA_ONLY",
                    "delegation_enabled": False,
                    "execution_enabled": False,
                })

        body = {
            "schema": SCHEMA,
            "status": "READY",
            "reason": "A2A_AGENT_CARD_PROJECTED",
            "protocol_version": A2A_PROTOCOL_VERSION,
            "release_baseline": A2A_RELEASE_BASELINE,
            "connector_id": connector_id,
            "agent": {
                "name": name,
                "description": description,
                "version": agent_version,
            },
            "interfaces": interfaces,
            "capabilities": {
                str(k): bool(v) if isinstance(v, bool) else False
                for k, v in sorted(caps.items())
            },
            "default_input_modes": sorted(set(str(x) for x in default_inputs if str(x).strip())),
            "default_output_modes": sorted(set(str(x) for x in default_outputs if str(x).strip())),
            "eligible_skills": eligible,
            "denied_skills": denied,
            "network_access": "DISABLED",
            "credential_access": "NONE",
            "live_message_send": "DISABLED",
            "live_stream": "DISABLED",
            "live_task_runtime": "DISABLED",
            "external_delegation": "DISABLED",
            "agent_authority_trusted": False,
            "authority_source": "LOM_LOCAL_REGISTRIES",
            "autonomous_ceiling": AUTONOMOUS_CEILING,
            "execution_authority": EXECUTION_AUTHORITY,
            "production_authority": PRODUCTION_AUTHORITY,
            "protected_main_merge": PROTECTED_MAIN_MERGE,
        }
    except ValueError as exc:
        return _hold(str(exc))
    return {**body, "projection_digest": digest(body)}


def _part_type(part: dict[str, Any]) -> str:
    if not isinstance(part, dict):
        raise ValueError("A2A_PART_INVALID")
    present = [key for key in ("text", "raw", "url", "data") if key in part and part.get(key) is not None]
    if len(present) != 1:
        raise ValueError("A2A_PART_CONTENT_INVALID")
    return present[0]


def project_message_metadata(message: dict[str, Any]) -> dict[str, Any]:
    try:
        if not isinstance(message, dict):
            raise ValueError("A2A_MESSAGE_INVALID")
        role = str(message.get("role") or "").strip()
        if role not in {"ROLE_USER", "ROLE_AGENT"}:
            raise ValueError("A2A_MESSAGE_ROLE_INVALID")
        parts = message.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ValueError("A2A_MESSAGE_PARTS_REQUIRED")
        types = [_part_type(part) for part in parts]
        body = {
            "status": "READY",
            "role": role,
            "message_id_present": bool(str(message.get("messageId") or "").strip()),
            "task_id_present": bool(str(message.get("taskId") or "").strip()),
            "context_id_present": bool(str(message.get("contextId") or "").strip()),
            "part_types": types,
            "content_forwarded": False,
            "message_authority": "NON_AUTHORITATIVE_COMMUNICATION",
        }
    except ValueError as exc:
        return {"status": "HOLD", "reason": str(exc), "content_forwarded": False}
    return {**body, "message_digest": digest(body)}


def _artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        raise ValueError("A2A_ARTIFACT_INVALID")
    artifact_id = str(artifact.get("artifactId") or "").strip()
    name = str(artifact.get("name") or "").strip()
    parts = artifact.get("parts")
    if not artifact_id or not name or not isinstance(parts, list) or not parts:
        raise ValueError("A2A_ARTIFACT_IDENTITY_INVALID")
    return {
        "artifact_id": artifact_id,
        "name": name,
        "part_types": [_part_type(part) for part in parts],
        "content_forwarded": False,
        "authoritative_without_lom_verification": False,
    }


def validate_task_envelope(task: dict[str, Any]) -> dict[str, Any]:
    try:
        if not isinstance(task, dict):
            raise ValueError("A2A_TASK_INVALID")
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            raise ValueError("A2A_TASK_ID_REQUIRED")
        status = task.get("status")
        if not isinstance(status, dict):
            raise ValueError("A2A_TASK_STATUS_REQUIRED")
        state = str(status.get("state") or "").strip()
        if state not in TASK_STATES:
            raise ValueError("A2A_TASK_STATE_INVALID")
        if state in HUMAN_GATE_STATES:
            reason = "A2A_INPUT_REQUIRED" if state == "TASK_STATE_INPUT_REQUIRED" else "A2A_AUTH_REQUIRED"
            return {
                "decision": "HUMAN_GATE",
                "reason": reason,
                "task_id": task_id,
                "state": state,
                "auto_response": "FORBIDDEN",
                "credential_forwarding": "FORBIDDEN",
                "external_delegation": "DISABLED",
                "network_action": "DISABLED",
            }

        artifacts_raw = task.get("artifacts") or []
        if not isinstance(artifacts_raw, list):
            raise ValueError("A2A_TASK_ARTIFACTS_INVALID")
        artifacts = [_artifact_metadata(row) for row in artifacts_raw]
        if state == "TASK_STATE_COMPLETED" and not artifacts:
            raise ValueError("A2A_COMPLETED_TASK_ARTIFACT_REQUIRED")

        history = task.get("history") or []
        if not isinstance(history, list):
            raise ValueError("A2A_TASK_HISTORY_INVALID")
        history_meta = [project_message_metadata(row) for row in history]
        if any(row.get("status") != "READY" for row in history_meta):
            raise ValueError("A2A_TASK_HISTORY_MESSAGE_INVALID")

        body = {
            "decision": "ALLOW_METADATA_ONLY",
            "reason": "A2A_TASK_ENVELOPE_VALID",
            "task_id": task_id,
            "context_id_present": bool(str(task.get("contextId") or "").strip()),
            "state": state,
            "artifacts": artifacts,
            "history": history_meta,
            "artifact_content_forwarded": False,
            "message_content_forwarded": False,
            "artifact_requires_lom_verification": True,
            "task_runtime": "DISABLED",
            "network_action": "DISABLED",
        }
    except ValueError as exc:
        return {
            "decision": "HOLD",
            "reason": str(exc),
            "task_runtime": "DISABLED",
            "network_action": "DISABLED",
        }
    return {**body, "task_digest": digest(body)}


def validate_a2a_projection(projection: dict[str, Any]) -> dict[str, str]:
    if not isinstance(projection, dict) or projection.get("schema") != SCHEMA:
        return {"status": "HOLD", "reason": "A2A_PROJECTION_SCHEMA_INVALID"}
    for key, expected in (
        ("autonomous_ceiling", AUTONOMOUS_CEILING),
        ("execution_authority", EXECUTION_AUTHORITY),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("protected_main_merge", PROTECTED_MAIN_MERGE),
    ):
        if projection.get(key) != expected:
            return {"status": "HOLD", "reason": f"{key.upper()}_WEAKENED"}
    required = {
        "network_access": "DISABLED",
        "credential_access": "NONE",
        "live_message_send": "DISABLED",
        "live_stream": "DISABLED",
        "live_task_runtime": "DISABLED",
        "external_delegation": "DISABLED",
        "agent_authority_trusted": False,
    }
    for key, expected in required.items():
        if projection.get(key) != expected:
            return {"status": "HOLD", "reason": f"A2A_INVARIANT_WEAKENED:{key}"}
    body = {k: v for k, v in projection.items() if k != "projection_digest"}
    if projection.get("projection_digest") != digest(body):
        return {"status": "HOLD", "reason": "A2A_PROJECTION_DIGEST_MISMATCH"}
    if projection.get("status") != "READY":
        return {"status": "HOLD", "reason": str(projection.get("reason") or "A2A_PROJECTION_HOLD")}
    for skill in projection.get("eligible_skills") or []:
        if skill.get("authority_source") != "LOM_LOCAL_BINDING":
            return {"status": "HOLD", "reason": "A2A_LOCAL_BINDING_REQUIRED"}
        if skill.get("delegation_enabled") is not False or skill.get("execution_enabled") is not False:
            return {"status": "HOLD", "reason": "A2A_EXECUTION_OR_DELEGATION_FORBIDDEN_P1"}
    return {"status": "READY", "reason": "A2A_PROJECTION_VALID"}
