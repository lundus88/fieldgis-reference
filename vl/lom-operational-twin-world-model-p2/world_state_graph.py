from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

WORLD_SCHEMA = "lom.world-state-graph/1"
TWIN_SCHEMA = "lom.operational-twin/1"
SOURCE_REGISTRY_VERSION = "2.0"

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _authority() -> dict[str, Any]:
    return {
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "self_approval": "FORBIDDEN",
        "database_mutation": "DISABLED",
        "connector_execution": "DISABLED",
    }


def _hold(reason: str, *, violations: Iterable[str] = ()) -> dict[str, Any]:
    payload = {
        "schema": WORLD_SCHEMA,
        "status": "HOLD",
        "reason": reason,
        "nodes": [],
        "edges": [],
        "violations": sorted(set(str(x) for x in violations if x)),
        "attention_required": True,
        **_authority(),
    }
    return {**payload, "graph_digest": digest(payload)}


def _source_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(registry, dict) or registry.get("version") != SOURCE_REGISTRY_VERSION:
        raise ValueError("SOURCE_REGISTRY_V2_REQUIRED")
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("SOURCE_REGISTRY_SOURCES_REQUIRED")

    out: dict[str, dict[str, Any]] = {}
    objectives: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("SOURCE_DECLARATION_INVALID")
        project_id = str(source.get("project_id") or "").strip()
        objective_id = str(source.get("objective_id") or "").strip()
        name = str(source.get("name") or "").strip()
        mode = source.get("mode")
        if not project_id or not objective_id or not name:
            raise ValueError("SOURCE_IDENTITY_REQUIRED")
        if project_id in out:
            raise ValueError("DUPLICATE_PROJECT_ID")
        if objective_id in objectives:
            raise ValueError("DUPLICATE_OBJECTIVE_ID")
        if mode == "READ_ONLY":
            if not source.get("repository") or not source.get("default_branch"):
                raise ValueError("READ_ONLY_SOURCE_REPOSITORY_REQUIRED")
        elif mode == "UNREGISTERED_HOLD":
            if not source.get("hold_reason"):
                raise ValueError("UNREGISTERED_SOURCE_HOLD_REASON_REQUIRED")
        else:
            raise ValueError("UNKNOWN_SOURCE_MODE")
        out[project_id] = dict(source)
        objectives.add(objective_id)
    return out


def _twin_index(
    twins: Iterable[dict[str, Any]],
    projects: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for twin in twins:
        if not isinstance(twin, dict) or twin.get("schema") != TWIN_SCHEMA:
            raise ValueError("OPERATIONAL_TWIN_SCHEMA_INVALID")
        project_id = str(twin.get("project_id") or "").strip()
        if not project_id:
            raise ValueError("TWIN_PROJECT_ID_REQUIRED")
        if project_id not in projects:
            raise ValueError("TWIN_PROJECT_NOT_REGISTERED")
        if project_id in out:
            raise ValueError("DUPLICATE_PROJECT_TWIN")
        if twin.get("production_authority") != PRODUCTION_AUTHORITY:
            raise ValueError("TWIN_PRODUCTION_AUTHORITY_WEAKENED")
        if twin.get("protected_main_merge") != PROTECTED_MAIN_MERGE:
            raise ValueError("TWIN_PROTECTED_MAIN_AUTHORITY_WEAKENED")
        if twin.get("execution_authority") != EXECUTION_AUTHORITY:
            raise ValueError("TWIN_EXECUTION_AUTHORITY_WEAKENED")
        if not twin.get("snapshot_digest"):
            raise ValueError("TWIN_SNAPSHOT_DIGEST_REQUIRED")
        out[project_id] = dict(twin)
    return out


def _dependency_edges(
    dependencies: Iterable[dict[str, Any]],
    projects: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in dependencies:
        if not isinstance(item, dict):
            raise ValueError("DEPENDENCY_DECLARATION_INVALID")
        downstream = str(item.get("downstream_project_id") or "").strip()
        upstream = str(item.get("upstream_project_id") or "").strip()
        evidence_ref = str(item.get("evidence_ref") or "").strip()
        if not downstream or not upstream:
            raise ValueError("DEPENDENCY_PROJECT_IDS_REQUIRED")
        if downstream not in projects or upstream not in projects:
            raise ValueError("DEPENDENCY_PROJECT_NOT_REGISTERED")
        if downstream == upstream:
            raise ValueError("SELF_DEPENDENCY_FORBIDDEN")
        if not evidence_ref:
            raise ValueError("DEPENDENCY_EVIDENCE_REQUIRED")
        key = (downstream, upstream, evidence_ref)
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "edge_id": "dep:" + digest(key)[7:23],
            "type": "DEPENDS_ON",
            "from": f"project:{downstream}",
            "to": f"project:{upstream}",
            "downstream_project_id": downstream,
            "upstream_project_id": upstream,
            "evidence_ref": evidence_ref,
        })
    return sorted(edges, key=lambda x: (x["downstream_project_id"], x["upstream_project_id"], x["evidence_ref"]))


def _dependency_cycle(edges: list[dict[str, Any]]) -> bool:
    graph: dict[str, set[str]] = {}
    nodes: set[str] = set()
    for edge in edges:
        downstream = edge["downstream_project_id"]
        upstream = edge["upstream_project_id"]
        graph.setdefault(downstream, set()).add(upstream)
        nodes.update((downstream, upstream))

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, set()):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(nodes))


def build_world_state_graph(
    source_registry: dict[str, Any],
    twins: Iterable[dict[str, Any]],
    *,
    dependencies: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    try:
        projects = _source_index(source_registry)
        twin_by_project = _twin_index(twins, projects)
        dependency_edges = _dependency_edges(dependencies, projects)
    except ValueError as exc:
        return _hold(str(exc))

    missing_twins = sorted(set(projects) - set(twin_by_project))
    if missing_twins:
        return _hold(
            "OPERATIONAL_TWIN_COVERAGE_INCOMPLETE",
            violations=[f"TWIN_MISSING:{project_id}" for project_id in missing_twins],
        )

    if _dependency_cycle(dependency_edges):
        return _hold("DEPENDENCY_CYCLE_DETECTED")

    upstream_by_downstream: dict[str, list[str]] = {}
    for edge in dependency_edges:
        upstream_by_downstream.setdefault(edge["downstream_project_id"], []).append(edge["upstream_project_id"])

    project_nodes: list[dict[str, Any]] = []
    objective_nodes: list[dict[str, Any]] = []
    has_objective_edges: list[dict[str, Any]] = []

    for project_id, source in sorted(projects.items()):
        twin = twin_by_project[project_id]
        upstream_ids = sorted(set(upstream_by_downstream.get(project_id, [])))
        upstream_attention = sorted(
            upstream
            for upstream in upstream_ids
            if twin_by_project[upstream].get("status") in {"HOLD", "REVIEW"}
            or twin_by_project[upstream].get("action_class") in {"HOLD", "HUMAN_REVIEW"}
        )
        local_attention = (
            twin.get("status") in {"HOLD", "REVIEW"}
            or twin.get("action_class") in {"HOLD", "HUMAN_REVIEW"}
        )
        project_nodes.append({
            "node_id": f"project:{project_id}",
            "type": "PROJECT",
            "project_id": project_id,
            "name": source["name"],
            "repository": source.get("repository"),
            "source_mode": source.get("mode"),
            "twin_status": twin.get("status"),
            "action_class": twin.get("action_class"),
            "reason": twin.get("reason"),
            "next_action": twin.get("next_action"),
            "snapshot_digest": twin.get("snapshot_digest"),
            "dependency_attention_from": upstream_attention,
            "attention_required": bool(local_attention or upstream_attention),
        })
        objective_id = source["objective_id"]
        objective_nodes.append({
            "node_id": f"objective:{objective_id}",
            "type": "OBJECTIVE",
            "objective_id": objective_id,
            "project_id": project_id,
        })
        has_objective_edges.append({
            "edge_id": f"objective-link:{project_id}",
            "type": "HAS_OBJECTIVE",
            "from": f"project:{project_id}",
            "to": f"objective:{objective_id}",
        })

    nodes = sorted(project_nodes + objective_nodes, key=lambda x: x["node_id"])
    edges = sorted(has_objective_edges + dependency_edges, key=lambda x: (x["type"], x["from"], x["to"], x["edge_id"]))
    attention_required = any(node.get("attention_required") for node in project_nodes)

    graph_payload = {
        "schema": WORLD_SCHEMA,
        "status": "READY",
        "reason": "WORLD_STATE_GRAPH_READY",
        "source_registry_version": SOURCE_REGISTRY_VERSION,
        "project_count": len(project_nodes),
        "objective_count": len(objective_nodes),
        "dependency_count": len(dependency_edges),
        "nodes": nodes,
        "edges": edges,
        "violations": [],
        "attention_required": attention_required,
        **_authority(),
    }
    return {**graph_payload, "graph_digest": digest(graph_payload)}


def validate_world_state_graph(graph: dict[str, Any]) -> dict[str, str]:
    if not isinstance(graph, dict) or graph.get("schema") != WORLD_SCHEMA:
        return {"status": "HOLD", "reason": "WORLD_GRAPH_SCHEMA_INVALID"}
    if graph.get("autonomous_ceiling") != AUTONOMOUS_CEILING:
        return {"status": "HOLD", "reason": "AUTONOMOUS_CEILING_WEAKENED"}
    if graph.get("execution_authority") != EXECUTION_AUTHORITY:
        return {"status": "HOLD", "reason": "EXECUTION_AUTHORITY_WEAKENED"}
    if graph.get("production_authority") != PRODUCTION_AUTHORITY:
        return {"status": "HOLD", "reason": "PRODUCTION_AUTHORITY_WEAKENED"}
    if graph.get("protected_main_merge") != PROTECTED_MAIN_MERGE:
        return {"status": "HOLD", "reason": "PROTECTED_MAIN_AUTHORITY_WEAKENED"}
    if graph.get("database_mutation") != "DISABLED" or graph.get("connector_execution") != "DISABLED":
        return {"status": "HOLD", "reason": "WORLD_GRAPH_WRITE_AUTHORITY_FORBIDDEN"}

    body = {k: v for k, v in graph.items() if k != "graph_digest"}
    if graph.get("graph_digest") != digest(body):
        return {"status": "HOLD", "reason": "WORLD_GRAPH_DIGEST_MISMATCH"}

    if graph.get("status") == "HOLD":
        return {"status": "HOLD", "reason": str(graph.get("reason") or "WORLD_GRAPH_HOLD")}
    if graph.get("status") != "READY":
        return {"status": "HOLD", "reason": "WORLD_GRAPH_STATUS_UNKNOWN"}
    return {"status": "READY", "reason": "WORLD_STATE_GRAPH_VALID"}
