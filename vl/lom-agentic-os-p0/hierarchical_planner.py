from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Iterable

from intelligence_core import HUMAN_ONLY

SCHEMA = "lom.hierarchical-plan/1"
REPLAN_SCHEMA = "lom.hierarchical-replan/1"

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"

ALLOWED_RISK = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_TRIGGERS = {
    "DEPENDENCY_FAILED",
    "VALIDATION_FAILED",
    "TOOL_UNAVAILABLE",
    "EVIDENCE_CHANGED",
    "ASSUMPTION_INVALIDATED",
}
MAX_NODES = 64
MAX_DEPTH = 5
MAX_AUTONOMOUS_UNCERTAINTY = 0.60
RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _hold(reason: str, *, objective_id: str = "", schema: str = SCHEMA) -> dict[str, Any]:
    body = {
        "schema": schema,
        "objective_id": objective_id,
        "status": "HOLD",
        "reason": reason,
        "execution_authority": EXECUTION_AUTHORITY,
        "execution_performed": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "authority_widening": "DISABLED",
        "self_approval": "FORBIDDEN",
    }
    return {**body, "digest": digest(body)}


def _human_gate(reason: str, *, objective_id: str = "", schema: str = SCHEMA) -> dict[str, Any]:
    body = {
        "schema": schema,
        "objective_id": objective_id,
        "status": "HUMAN_GATE",
        "reason": reason,
        "execution_authority": EXECUTION_AUTHORITY,
        "execution_performed": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "authority_widening": "DISABLED",
        "self_approval": "FORBIDDEN",
    }
    return {**body, "digest": digest(body)}


@dataclass(frozen=True)
class PlanNode:
    node_id: str
    parent_id: str | None
    action_id: str
    capability_id: str
    evidence_ids: tuple[str, ...]
    success_criteria: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    risk: str = "LOW"
    reversible: bool = True
    environment: str = "NON_PRODUCTION"
    uncertainty: float = 0.0
    assumptions: tuple[str, ...] = ()

    def validate_basic(self) -> None:
        if not self.node_id.strip():
            raise ValueError("NODE_ID_REQUIRED")
        if not self.action_id.strip() or not self.capability_id.strip():
            raise ValueError("NODE_ACTION_OR_CAPABILITY_REQUIRED")
        if not self.evidence_ids or any(not str(x).strip() for x in self.evidence_ids):
            raise ValueError("NODE_EVIDENCE_REQUIRED")
        if not self.success_criteria or any(not str(x).strip() for x in self.success_criteria):
            raise ValueError("NODE_SUCCESS_CRITERIA_REQUIRED")
        if self.risk not in ALLOWED_RISK:
            raise ValueError("NODE_RISK_INVALID")
        if not isinstance(self.reversible, bool):
            raise ValueError("NODE_REVERSIBILITY_BOOL_REQUIRED")
        if not isinstance(self.uncertainty, (int, float)) or isinstance(self.uncertainty, bool):
            raise ValueError("NODE_UNCERTAINTY_NOT_NUMERIC")
        if not math.isfinite(float(self.uncertainty)) or not 0.0 <= float(self.uncertainty) <= 1.0:
            raise ValueError("NODE_UNCERTAINTY_OUT_OF_RANGE")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("DUPLICATE_DEPENDENCY")
        if self.node_id in self.dependencies:
            raise ValueError("SELF_DEPENDENCY")


@dataclass(frozen=True)
class ReplanSignal:
    plan_digest: str
    trigger: str
    trigger_evidence_refs: tuple[str, ...]
    completed_node_ids: tuple[str, ...]
    evidence_fresh: bool
    authority_unchanged: bool
    scope_unchanged: bool
    risk: str
    production: bool = False


def _canonical_node(node: PlanNode) -> dict[str, Any]:
    raw = asdict(node)
    raw["evidence_ids"] = list(node.evidence_ids)
    raw["success_criteria"] = list(node.success_criteria)
    raw["dependencies"] = list(node.dependencies)
    raw["assumptions"] = list(node.assumptions)
    return raw


def _index_nodes(nodes: Iterable[PlanNode]) -> dict[str, PlanNode]:
    rows = list(nodes)
    if not rows:
        raise ValueError("PLAN_NODES_REQUIRED")
    if len(rows) > MAX_NODES:
        raise ValueError("PLAN_NODE_BUDGET_EXCEEDED")
    out: dict[str, PlanNode] = {}
    for node in rows:
        node.validate_basic()
        if node.node_id in out:
            raise ValueError("DUPLICATE_NODE_ID")
        out[node.node_id] = node
    return out


def _validate_parent_graph(nodes: dict[str, PlanNode]) -> tuple[str, dict[str, int]]:
    roots = [node.node_id for node in nodes.values() if node.parent_id is None]
    if len(roots) != 1:
        raise ValueError("SINGLE_ROOT_REQUIRED")
    root = roots[0]
    depths: dict[str, int] = {}

    def depth(node_id: str, trail: set[str]) -> int:
        if node_id in depths:
            return depths[node_id]
        if node_id in trail:
            raise ValueError("PARENT_CYCLE")
        node = nodes[node_id]
        if node.parent_id is None:
            depths[node_id] = 0
            return 0
        if node.parent_id not in nodes:
            raise ValueError("UNKNOWN_PARENT")
        value = 1 + depth(node.parent_id, trail | {node_id})
        if value > MAX_DEPTH:
            raise ValueError("PLAN_DEPTH_BUDGET_EXCEEDED")
        depths[node_id] = value
        return value

    for node_id in nodes:
        depth(node_id, set())
    return root, depths


def _validate_dependencies(nodes: dict[str, PlanNode]) -> list[list[str]]:
    for node in nodes.values():
        for dep in node.dependencies:
            if dep not in nodes:
                raise ValueError("UNKNOWN_DEPENDENCY")
        if node.parent_id is not None and node.parent_id not in node.dependencies:
            raise ValueError("PARENT_DEPENDENCY_REQUIRED")

    indegree = {node_id: 0 for node_id in nodes}
    children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for node in nodes.values():
        for dep in node.dependencies:
            indegree[node.node_id] += 1
            children[dep].append(node.node_id)

    current = sorted([node_id for node_id, degree in indegree.items() if degree == 0])
    waves: list[list[str]] = []
    visited = 0
    while current:
        waves.append(list(current))
        visited += len(current)
        next_wave: list[str] = []
        for node_id in current:
            for child in sorted(children[node_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_wave.append(child)
        current = sorted(next_wave)

    if visited != len(nodes):
        raise ValueError("DEPENDENCY_CYCLE")
    return waves


def _authority_gate(nodes: dict[str, PlanNode], objective_id: str) -> dict[str, Any] | None:
    for node in nodes.values():
        if node.action_id in HUMAN_ONLY:
            return _human_gate("HUMAN_ONLY_ACTION_IN_PLAN", objective_id=objective_id)
        if node.environment == "PRODUCTION":
            return _human_gate("PRODUCTION_NODE_REQUIRES_HUMAN", objective_id=objective_id)
        if node.environment != "NON_PRODUCTION":
            return _hold("UNKNOWN_ENVIRONMENT", objective_id=objective_id)
        if node.risk == "HIGH":
            return _human_gate("HIGH_RISK_NODE_REQUIRES_HUMAN", objective_id=objective_id)
        if not node.reversible:
            return _hold("REVERSIBILITY_REQUIRED", objective_id=objective_id)
        if float(node.uncertainty) > MAX_AUTONOMOUS_UNCERTAINTY:
            return _human_gate("UNCERTAINTY_REQUIRES_HUMAN_REVIEW", objective_id=objective_id)
    return None


def build_hierarchical_plan(
    *,
    objective_id: str,
    nodes: Iterable[PlanNode],
    parent_plan_digest: str | None = None,
    replan_count: int = 0,
) -> dict[str, Any]:
    if not str(objective_id or "").strip():
        return _hold("OBJECTIVE_ID_REQUIRED")
    if not isinstance(replan_count, int) or isinstance(replan_count, bool) or replan_count < 0:
        return _hold("REPLAN_COUNT_INVALID", objective_id=objective_id)

    try:
        indexed = _index_nodes(nodes)
        root, depths = _validate_parent_graph(indexed)
        waves = _validate_dependencies(indexed)
    except ValueError as exc:
        return _hold(str(exc), objective_id=objective_id)

    gate = _authority_gate(indexed, objective_id)
    if gate is not None:
        return gate

    serialized = [_canonical_node(indexed[node_id]) for node_id in sorted(indexed)]
    body = {
        "schema": SCHEMA,
        "objective_id": objective_id,
        "status": "PLAN_READY",
        "reason": "BOUNDED_HIERARCHICAL_PLAN_READY",
        "root_node_id": root,
        "nodes": serialized,
        "node_count": len(serialized),
        "max_depth_observed": max(depths.values()),
        "execution_waves": waves,
        "lineage": {
            "parent_plan_digest": parent_plan_digest,
            "replan_count": replan_count,
        },
        "plan_budget": {
            "max_nodes": MAX_NODES,
            "max_depth": MAX_DEPTH,
        },
        "replanning_policy": "EVIDENCE_TRIGGERED_ONLY",
        "execution_authority": EXECUTION_AUTHORITY,
        "execution_performed": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "authority_widening": "DISABLED",
        "self_approval": "FORBIDDEN",
    }
    return {**body, "plan_digest": digest(body)}


def validate_plan(plan: dict[str, Any]) -> dict[str, str]:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        return {"status": "HOLD", "reason": "PLAN_SCHEMA_INVALID"}
    if plan.get("status") != "PLAN_READY":
        return {"status": "HOLD", "reason": "PLAN_NOT_READY"}
    for key, expected in (
        ("execution_authority", EXECUTION_AUTHORITY),
        ("execution_performed", False),
        ("autonomous_ceiling", AUTONOMOUS_CEILING),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("protected_main_merge", PROTECTED_MAIN_MERGE),
        ("authority_widening", "DISABLED"),
        ("self_approval", "FORBIDDEN"),
    ):
        if plan.get(key) != expected:
            return {"status": "HOLD", "reason": f"PLAN_INVARIANT_WEAKENED:{key}"}
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    if plan.get("plan_digest") != digest(body):
        return {"status": "HOLD", "reason": "PLAN_DIGEST_MISMATCH"}
    return {"status": "READY", "reason": "PLAN_VALID"}


def evaluate_replan_signal(plan: dict[str, Any], signal: ReplanSignal) -> dict[str, Any]:
    validation = validate_plan(plan)
    if validation["status"] != "READY":
        return _hold("VALID_PLAN_REQUIRED", objective_id=str(plan.get("objective_id") or ""), schema=REPLAN_SCHEMA)
    objective_id = str(plan["objective_id"])

    if signal.plan_digest != plan.get("plan_digest"):
        return _hold("REPLAN_SOURCE_DIGEST_MISMATCH", objective_id=objective_id, schema=REPLAN_SCHEMA)
    if signal.trigger not in ALLOWED_TRIGGERS:
        return _hold("UNKNOWN_REPLAN_TRIGGER", objective_id=objective_id, schema=REPLAN_SCHEMA)
    if not signal.trigger_evidence_refs or any(not str(x).strip() for x in signal.trigger_evidence_refs):
        return _hold("REPLAN_TRIGGER_EVIDENCE_REQUIRED", objective_id=objective_id, schema=REPLAN_SCHEMA)
    if not signal.evidence_fresh:
        return _hold("REPLAN_EVIDENCE_STALE", objective_id=objective_id, schema=REPLAN_SCHEMA)
    if signal.risk not in ALLOWED_RISK:
        return _hold("REPLAN_RISK_INVALID", objective_id=objective_id, schema=REPLAN_SCHEMA)
    if signal.production or signal.risk == "HIGH":
        return _human_gate("REPLAN_HUMAN_BOUNDARY", objective_id=objective_id, schema=REPLAN_SCHEMA)
    if not signal.authority_unchanged:
        return _human_gate("REPLAN_AUTHORITY_CHANGE_REQUIRES_HUMAN", objective_id=objective_id, schema=REPLAN_SCHEMA)
    if not signal.scope_unchanged:
        return _human_gate("REPLAN_SCOPE_CHANGE_REQUIRES_HUMAN", objective_id=objective_id, schema=REPLAN_SCHEMA)

    node_ids = {str(row.get("node_id") or "") for row in plan.get("nodes") or []}
    completed = set(signal.completed_node_ids)
    if not completed.issubset(node_ids):
        return _hold("UNKNOWN_COMPLETED_NODE", objective_id=objective_id, schema=REPLAN_SCHEMA)

    body = {
        "schema": REPLAN_SCHEMA,
        "objective_id": objective_id,
        "status": "REPLAN_CANDIDATE",
        "reason": signal.trigger,
        "source_plan_digest": plan["plan_digest"],
        "completed_node_ids": sorted(completed),
        "mutable_node_ids": sorted(node_ids - completed),
        "trigger_evidence_refs": sorted(set(signal.trigger_evidence_refs)),
        "scope_change": "FORBIDDEN",
        "authority_change": "FORBIDDEN",
        "completed_node_mutation": "FORBIDDEN",
        "execution_authority": EXECUTION_AUTHORITY,
        "execution_performed": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "authority_widening": "DISABLED",
        "self_approval": "FORBIDDEN",
    }
    return {**body, "replan_signal_digest": digest(body)}


def prepare_replan(
    plan: dict[str, Any],
    signal: ReplanSignal,
    replacement_nodes: Iterable[PlanNode],
) -> dict[str, Any]:
    gate = evaluate_replan_signal(plan, signal)
    if gate.get("status") != "REPLAN_CANDIDATE":
        return gate

    previous_nodes = {
        str(row["node_id"]): row for row in plan.get("nodes") or []
    }
    replacements = list(replacement_nodes)
    replacement_ids = {node.node_id for node in replacements}
    if len(replacement_ids) != len(replacements):
        return _hold("DUPLICATE_REPLACEMENT_NODE", objective_id=plan["objective_id"], schema=REPLAN_SCHEMA)

    completed = set(gate["completed_node_ids"])
    mutable = set(gate["mutable_node_ids"])
    if replacement_ids != mutable:
        return _hold("REPLAN_MUST_REPLACE_EXACT_MUTABLE_SET", objective_id=plan["objective_id"], schema=REPLAN_SCHEMA)

    combined: list[PlanNode] = []
    for node_id in sorted(completed):
        row = previous_nodes[node_id]
        combined.append(PlanNode(
            node_id=row["node_id"],
            parent_id=row["parent_id"],
            action_id=row["action_id"],
            capability_id=row["capability_id"],
            evidence_ids=tuple(row["evidence_ids"]),
            success_criteria=tuple(row["success_criteria"]),
            dependencies=tuple(row["dependencies"]),
            risk=row["risk"],
            reversible=row["reversible"],
            environment=row["environment"],
            uncertainty=float(row["uncertainty"]),
            assumptions=tuple(row["assumptions"]),
        ))

    for node in replacements:
        old = previous_nodes[node.node_id]
        if node.action_id != old["action_id"] or node.capability_id != old["capability_id"]:
            return _human_gate("REPLAN_SCOPE_WIDENING_FORBIDDEN", objective_id=plan["objective_id"], schema=REPLAN_SCHEMA)
        if RISK_ORDER[node.risk] > RISK_ORDER[old["risk"]]:
            return _human_gate("REPLAN_RISK_WIDENING_FORBIDDEN", objective_id=plan["objective_id"], schema=REPLAN_SCHEMA)
        if node.environment != old["environment"]:
            return _human_gate("REPLAN_ENVIRONMENT_CHANGE_FORBIDDEN", objective_id=plan["objective_id"], schema=REPLAN_SCHEMA)
        combined.append(node)

    replanned = build_hierarchical_plan(
        objective_id=plan["objective_id"],
        nodes=combined,
        parent_plan_digest=plan["plan_digest"],
        replan_count=int((plan.get("lineage") or {}).get("replan_count", 0)) + 1,
    )
    if replanned.get("status") != "PLAN_READY":
        return replanned

    body = {
        "schema": REPLAN_SCHEMA,
        "objective_id": plan["objective_id"],
        "status": "REPLAN_READY",
        "reason": "BOUNDED_REPLAN_READY",
        "source_plan_digest": plan["plan_digest"],
        "new_plan_digest": replanned["plan_digest"],
        "replanned_plan": replanned,
        "completed_node_ids": sorted(completed),
        "completed_node_mutation": "FORBIDDEN",
        "scope_change": "FORBIDDEN",
        "authority_change": "FORBIDDEN",
        "execution_authority": EXECUTION_AUTHORITY,
        "execution_performed": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "self_approval": "FORBIDDEN",
    }
    return {**body, "replan_digest": digest(body)}


def execute_plan(*args, **kwargs):
    raise PermissionError("HIERARCHICAL_PLANNER_EXECUTION_FORBIDDEN")
