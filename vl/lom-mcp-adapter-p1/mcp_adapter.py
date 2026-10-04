from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

SCHEMA = "lom.mcp-adapter/1"
MCP_PROTOCOL_VERSION = "2026-07-28"
MCP_TASKS_EXTENSION = "io.modelcontextprotocol/tasks"

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"

TASK_STATUSES = {"working", "input_required", "completed", "cancelled", "failed"}
ALLOWED_ACTION = "READ_ONLY_OBSERVATION"
ALLOWED_CAPABILITY = "cap.observe.readonly"


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _hold(reason: str) -> dict[str, Any]:
    body = {
        "schema": SCHEMA,
        "status": "HOLD",
        "reason": reason,
        "eligible_tools": [],
        "denied_tools": [],
        "resources": [],
        "prompts": [],
        "tasks_extension": "DISABLED",
        "network_access": "DISABLED",
        "credential_access": "NONE",
        "server_authority_trusted": False,
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
    out = {}
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
    out = {}
    for action in actions:
        aid = str(action.get("action_id") or "").strip()
        if not aid or aid in out:
            raise ValueError("ACTION_ID_INVALID")
        out[aid] = dict(action)
    return out


def _validate_mcp_connector(connector: dict[str, Any]) -> None:
    if connector.get("status") != "certified-fixture":
        raise ValueError("MCP_CONNECTOR_NOT_CERTIFIED_FIXTURE")
    if connector.get("mode") != "read-only":
        raise ValueError("MCP_CONNECTOR_READ_ONLY_REQUIRED")
    if connector.get("allowed_operations") != ["read"]:
        raise ValueError("MCP_CONNECTOR_READ_ONLY_OPERATION_REQUIRED")
    if connector.get("external_runtime") is not False:
        raise ValueError("MCP_EXTERNAL_RUNTIME_FORBIDDEN_P1")
    if connector.get("credentials_required") is not False:
        raise ValueError("MCP_CREDENTIALS_FORBIDDEN_P1")
    if connector.get("protocol") != "mcp":
        raise ValueError("MCP_PROTOCOL_BINDING_REQUIRED")
    if connector.get("protocol_version") != MCP_PROTOCOL_VERSION:
        raise ValueError("MCP_PROTOCOL_VERSION_MISMATCH")
    if connector.get("network_access") != "DISABLED":
        raise ValueError("MCP_NETWORK_ACCESS_FORBIDDEN_P1")
    if connector.get("server_authority_trusted") is not False:
        raise ValueError("MCP_SERVER_AUTHORITY_MUST_BE_UNTRUSTED")


def _bindings(
    rows: Iterable[dict[str, Any]],
    connector: dict[str, Any],
    actions: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    scopes = set(connector.get("resource_scopes") or [])
    action = actions.get(ALLOWED_ACTION)
    if not action:
        raise ValueError("MCP_LOCAL_ACTION_NOT_REGISTERED")
    if (
        action.get("capability_id") != ALLOWED_CAPABILITY
        or action.get("max_risk") != "LOW"
        or action.get("reversible_required") is not True
        or action.get("non_production_only") is not True
    ):
        raise ValueError("MCP_LOCAL_ACTION_CONTRACT_INVALID")

    out = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("MCP_LOCAL_BINDING_INVALID")
        name = str(row.get("mcp_tool_name") or "").strip()
        if not name or name in out:
            raise ValueError("MCP_LOCAL_BINDING_TOOL_INVALID")
        if row.get("connector_id") != connector.get("id"):
            raise ValueError("MCP_LOCAL_BINDING_CONNECTOR_MISMATCH")
        if row.get("action_id") != ALLOWED_ACTION:
            raise ValueError("MCP_LOCAL_BINDING_ACTION_FORBIDDEN")
        if row.get("capability_id") != ALLOWED_CAPABILITY:
            raise ValueError("MCP_LOCAL_BINDING_CAPABILITY_FORBIDDEN")
        scope = str(row.get("resource_scope") or "").strip()
        if scope not in scopes:
            raise ValueError("MCP_LOCAL_BINDING_SCOPE_MISMATCH")
        out[name] = {
            "connector_id": connector["id"],
            "mcp_tool_name": name,
            "action_id": ALLOWED_ACTION,
            "capability_id": ALLOWED_CAPABILITY,
            "resource_scope": scope,
            "risk": "LOW",
            "authority_source": "LOM_LOCAL_BINDING",
        }
    return out


def _tool(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("MCP_TOOL_INVALID")
    name = str(row.get("name") or "").strip()
    schema = row.get("inputSchema")
    if not name:
        raise ValueError("MCP_TOOL_NAME_REQUIRED")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("MCP_TOOL_INPUT_SCHEMA_INVALID")
    annotations = row.get("annotations") or {}
    if not isinstance(annotations, dict):
        raise ValueError("MCP_TOOL_ANNOTATIONS_INVALID")
    hint = annotations.get("readOnlyHint")
    if hint is not None and not isinstance(hint, bool):
        raise ValueError("MCP_TOOL_READONLY_HINT_INVALID")
    return {
        "name": name,
        "description": str(row.get("description") or "").strip(),
        "input_schema_digest": digest(schema),
        "server_read_only_hint": hint,
        "server_annotations_trusted_for_authority": False,
    }


def _resources(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise ValueError("MCP_RESOURCES_INVALID")
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("MCP_RESOURCE_INVALID")
        uri = str(row.get("uri") or "").strip()
        name = str(row.get("name") or "").strip()
        if not uri or not name or uri in seen:
            raise ValueError("MCP_RESOURCE_IDENTITY_INVALID")
        seen.add(uri)
        out.append({"uri": uri, "name": name, "metadata_only": True, "content_forwarded": False})
    return sorted(out, key=lambda x: x["uri"])


def _prompts(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise ValueError("MCP_PROMPTS_INVALID")
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("MCP_PROMPT_INVALID")
        name = str(row.get("name") or "").strip()
        if not name or name in seen:
            raise ValueError("MCP_PROMPT_NAME_INVALID")
        seen.add(name)
        out.append({"name": name, "metadata_only": True, "prompt_content_forwarded": False})
    return sorted(out, key=lambda x: x["name"])


def compile_mcp_discovery_projection(
    *,
    connector_id: str,
    discovery: dict[str, Any],
    connector_registry: dict[str, Any],
    action_registry: dict[str, Any],
    local_bindings: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        connectors = _connector_index(connector_registry)
        actions = _action_index(action_registry)
        connector = connectors.get(connector_id)
        if connector is None:
            raise ValueError("MCP_CONNECTOR_NOT_REGISTERED")
        _validate_mcp_connector(connector)

        if not isinstance(discovery, dict):
            raise ValueError("MCP_DISCOVERY_INVALID")
        if discovery.get("protocol_version") != MCP_PROTOCOL_VERSION:
            raise ValueError("MCP_DISCOVERY_PROTOCOL_VERSION_MISMATCH")
        server = discovery.get("server")
        if not isinstance(server, dict) or not str(server.get("name") or "").strip() or not str(server.get("version") or "").strip():
            raise ValueError("MCP_SERVER_IDENTITY_INVALID")

        caps = discovery.get("capabilities")
        if not isinstance(caps, dict):
            raise ValueError("MCP_CAPABILITIES_INVALID")
        for key in ("tools", "resources", "prompts"):
            if not isinstance(caps.get(key, False), bool):
                raise ValueError("MCP_CAPABILITY_FLAG_INVALID")

        extension_rows = discovery.get("extensions") or []
        if not isinstance(extension_rows, list):
            raise ValueError("MCP_EXTENSIONS_INVALID")
        extensions = []
        for item in extension_rows:
            ext = item if isinstance(item, str) else str((item or {}).get("id") or "")
            ext = str(ext).strip()
            if not ext:
                raise ValueError("MCP_EXTENSION_ID_REQUIRED")
            extensions.append(ext)
        if len(extensions) != len(set(extensions)):
            raise ValueError("MCP_DUPLICATE_EXTENSION")

        bindings = _bindings(local_bindings, connector, actions)
        raw_tools = discovery.get("tools") or []
        if not isinstance(raw_tools, list):
            raise ValueError("MCP_TOOLS_INVALID")
        if raw_tools and not caps.get("tools", False):
            raise ValueError("MCP_TOOLS_WITHOUT_CAPABILITY")
        tools = [_tool(row) for row in raw_tools]
        names = [row["name"] for row in tools]
        if len(names) != len(set(names)):
            raise ValueError("MCP_DUPLICATE_TOOL")

        eligible, denied = [], []
        for tool in sorted(tools, key=lambda x: x["name"]):
            binding = bindings.get(tool["name"])
            if binding is None:
                denied.append({
                    "name": tool["name"],
                    "decision": "HOLD",
                    "reason": "UNBOUND_MCP_TOOL",
                    "server_read_only_hint": tool["server_read_only_hint"],
                    "server_annotations_trusted_for_authority": False,
                })
            else:
                eligible.append({
                    **tool,
                    **binding,
                    "decision": "ALLOW_METADATA_ONLY",
                    "execution_enabled": False,
                })

        resources = _resources(discovery.get("resources"))
        prompts = _prompts(discovery.get("prompts"))
        if resources and not caps.get("resources", False):
            raise ValueError("MCP_RESOURCES_WITHOUT_CAPABILITY")
        if prompts and not caps.get("prompts", False):
            raise ValueError("MCP_PROMPTS_WITHOUT_CAPABILITY")

        body = {
            "schema": SCHEMA,
            "status": "READY",
            "reason": "MCP_DISCOVERY_PROJECTED",
            "protocol_version": MCP_PROTOCOL_VERSION,
            "connector_id": connector_id,
            "server": {"name": server["name"], "version": server["version"]},
            "capabilities": {k: bool(caps.get(k, False)) for k in ("tools", "resources", "prompts")},
            "extensions": sorted(extensions),
            "eligible_tools": eligible,
            "denied_tools": denied,
            "resources": resources,
            "prompts": prompts,
            "tasks_extension": "METADATA_ONLY" if MCP_TASKS_EXTENSION in extensions else "NOT_ADVERTISED",
            "task_runtime": "DISABLED",
            "live_tool_call": "DISABLED",
            "live_resource_read": "DISABLED",
            "live_prompt_fetch": "DISABLED",
            "network_access": "DISABLED",
            "credential_access": "NONE",
            "server_authority_trusted": False,
            "authority_source": "LOM_LOCAL_REGISTRIES",
            "autonomous_ceiling": AUTONOMOUS_CEILING,
            "execution_authority": EXECUTION_AUTHORITY,
            "production_authority": PRODUCTION_AUTHORITY,
            "protected_main_merge": PROTECTED_MAIN_MERGE,
        }
    except ValueError as exc:
        return _hold(str(exc))
    return {**body, "projection_digest": digest(body)}


def validate_task_handle(task: dict[str, Any], *, tasks_extension_declared: bool) -> dict[str, Any]:
    if not tasks_extension_declared:
        return {"decision": "HOLD", "reason": "MCP_TASKS_EXTENSION_NOT_DECLARED"}
    if not isinstance(task, dict):
        return {"decision": "HOLD", "reason": "MCP_TASK_INVALID"}
    task_id = str(task.get("taskId") or "").strip()
    status = str(task.get("status") or "").strip()
    if len(task_id) < 16:
        return {"decision": "HOLD", "reason": "MCP_TASK_ID_TOO_WEAK"}
    if status not in TASK_STATUSES:
        return {"decision": "HOLD", "reason": "MCP_TASK_STATUS_INVALID"}
    if not str(task.get("createdAt") or "").strip() or not str(task.get("lastUpdatedAt") or "").strip():
        return {"decision": "HOLD", "reason": "MCP_TASK_TIMESTAMPS_REQUIRED"}
    ttl = task.get("ttlMs")
    poll = task.get("pollIntervalMs")
    if ttl is not None and (not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 0):
        return {"decision": "HOLD", "reason": "MCP_TASK_TTL_INVALID"}
    if poll is not None and (not isinstance(poll, int) or isinstance(poll, bool) or poll <= 0):
        return {"decision": "HOLD", "reason": "MCP_TASK_POLL_INTERVAL_INVALID"}
    if status == "completed" and not isinstance(task.get("result"), dict):
        return {"decision": "HOLD", "reason": "MCP_COMPLETED_TASK_RESULT_REQUIRED"}
    if status == "failed" and not isinstance(task.get("error"), dict):
        return {"decision": "HOLD", "reason": "MCP_FAILED_TASK_ERROR_REQUIRED"}
    if status == "input_required":
        reqs = task.get("inputRequests")
        if not isinstance(reqs, dict) or not reqs:
            return {"decision": "HOLD", "reason": "MCP_INPUT_REQUESTS_REQUIRED"}
        return {
            "decision": "HUMAN_GATE",
            "reason": "MCP_TASK_INPUT_REQUIRED",
            "task_id": task_id,
            "status": status,
            "auto_response": "FORBIDDEN",
            "network_action": "DISABLED",
        }
    body = {
        "decision": "ALLOW_METADATA_ONLY",
        "reason": "MCP_TASK_HANDLE_VALID",
        "task_id": task_id,
        "status": status,
        "ttl_ms": ttl,
        "poll_interval_ms": poll,
        "network_action": "DISABLED",
        "task_persistence": "NONE",
    }
    return {**body, "task_digest": digest(body)}


def validate_mcp_projection(projection: dict[str, Any]) -> dict[str, str]:
    if not isinstance(projection, dict) or projection.get("schema") != SCHEMA:
        return {"status": "HOLD", "reason": "MCP_PROJECTION_SCHEMA_INVALID"}
    for key, expected in (
        ("autonomous_ceiling", AUTONOMOUS_CEILING),
        ("execution_authority", EXECUTION_AUTHORITY),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("protected_main_merge", PROTECTED_MAIN_MERGE),
    ):
        if projection.get(key) != expected:
            return {"status": "HOLD", "reason": f"{key.upper()}_WEAKENED"}
    if projection.get("network_access") != "DISABLED":
        return {"status": "HOLD", "reason": "MCP_LIVE_NETWORK_FORBIDDEN_P1"}
    if projection.get("credential_access") != "NONE":
        return {"status": "HOLD", "reason": "MCP_CREDENTIAL_ACCESS_FORBIDDEN_P1"}
    if projection.get("server_authority_trusted") is not False:
        return {"status": "HOLD", "reason": "MCP_SERVER_AUTHORITY_TRUST_FORBIDDEN"}
    if projection.get("live_tool_call") != "DISABLED":
        return {"status": "HOLD", "reason": "MCP_LIVE_TOOL_CALL_FORBIDDEN_P1"}
    if projection.get("task_runtime") != "DISABLED":
        return {"status": "HOLD", "reason": "MCP_TASK_RUNTIME_FORBIDDEN_P1"}
    body = {k: v for k, v in projection.items() if k != "projection_digest"}
    if projection.get("projection_digest") != digest(body):
        return {"status": "HOLD", "reason": "MCP_PROJECTION_DIGEST_MISMATCH"}
    if projection.get("status") != "READY":
        return {"status": "HOLD", "reason": str(projection.get("reason") or "MCP_PROJECTION_HOLD")}
    for tool in projection.get("eligible_tools") or []:
        if tool.get("authority_source") != "LOM_LOCAL_BINDING" or tool.get("execution_enabled") is not False:
            return {"status": "HOLD", "reason": "MCP_LOCAL_AUTHORITY_BINDING_REQUIRED"}
    return {"status": "READY", "reason": "MCP_PROJECTION_VALID"}
