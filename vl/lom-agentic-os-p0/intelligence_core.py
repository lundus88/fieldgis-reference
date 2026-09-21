from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Iterable

HUMAN_ONLY = {
    "PRODUCTION_RELEASE","PROTECTED_MAIN_MERGE","PRODUCTION_DATA_MUTATION",
    "AUTHORITY_WIDENING","AUTH_SECURITY_POLICY_CHANGE","DATA_DELETION",
    "CUSTOMER_COMMITMENT","BID_SUBMISSION","PRICING_COMMITMENT",
    "CONTRACT_COMMITMENT","FINANCIAL_COMMITMENT"
}

def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    capability_id: str
    certified: bool
    non_production_only: bool
    max_risk: str = "LOW"

@dataclass(frozen=True)
class ModelRoute:
    route_id: str
    provider: str
    certified: bool
    supported: bool
    non_production_only: bool
    quality: int
    reliability: int
    latency: int
    cost: int

@dataclass(frozen=True)
class Objective:
    objective_id: str
    action_id: str
    capability_id: str
    evidence_ids: tuple[str, ...]
    requested_tool: str | None = None
    risk: str = "LOW"

class IntelligenceCore:
    def __init__(self, tools: Iterable[ToolSpec], routes: Iterable[ModelRoute]):
        self.tools = {t.tool_id: t for t in tools}
        self.routes = {r.route_id: r for r in routes}

    def authority_decision(self, objective: Objective) -> dict[str, Any]:
        if objective.action_id in HUMAN_ONLY:
            return {"decision":"HUMAN_GATE","reason":"HUMAN_ONLY_ACTION"}
        if not objective.objective_id or not objective.capability_id:
            return {"decision":"HOLD","reason":"OBJECTIVE_OR_CAPABILITY_MISSING"}
        if not objective.evidence_ids:
            return {"decision":"HOLD","reason":"EVIDENCE_REQUIRED"}
        if objective.risk not in {"LOW","MEDIUM","HIGH"}:
            return {"decision":"HOLD","reason":"UNKNOWN_RISK"}
        if objective.risk == "HIGH":
            return {"decision":"HUMAN_GATE","reason":"HIGH_RISK"}
        return {"decision":"ALLOW","reason":"BOUNDED_NON_PRODUCTION"}

    def discover_tool(self, objective: Objective) -> dict[str, Any]:
        if not objective.requested_tool:
            return {"decision":"HOLD","reason":"TOOL_REQUIRED"}
        tool = self.tools.get(objective.requested_tool)
        if tool is None:
            return {"decision":"HOLD","reason":"UNKNOWN_TOOL"}
        if not tool.certified or not tool.non_production_only:
            return {"decision":"HOLD","reason":"TOOL_NOT_ELIGIBLE"}
        if tool.capability_id != objective.capability_id:
            return {"decision":"HOLD","reason":"TOOL_CAPABILITY_MISMATCH"}
        if tool.max_risk == "LOW" and objective.risk != "LOW":
            return {"decision":"HOLD","reason":"TOOL_RISK_EXCEEDED"}
        return {"decision":"ALLOW","reason":"CERTIFIED_TOOL","tool_id":tool.tool_id}

    def route_model(self) -> dict[str, Any]:
        eligible = [
            r for r in self.routes.values()
            if r.certified and r.supported and r.non_production_only
        ]
        if not eligible:
            return {"decision":"HOLD","reason":"NO_ELIGIBLE_MODEL_ROUTE"}
        # deterministic quality/reliability first, then lower latency/cost
        chosen = sorted(
            eligible,
            key=lambda r: (-r.quality, -r.reliability, r.latency, r.cost, r.route_id),
        )[0]
        return {"decision":"ALLOW","reason":"CERTIFIED_ROUTE","route_id":chosen.route_id}

    def plan(self, objective: Objective) -> dict[str, Any]:
        authority = self.authority_decision(objective)
        if authority["decision"] != "ALLOW":
            return {"schema":"lom.agentic-plan/1", **authority, "steps":[]}

        tool = self.discover_tool(objective)
        if tool["decision"] != "ALLOW":
            return {"schema":"lom.agentic-plan/1", **tool, "steps":[]}

        route = self.route_model()
        if route["decision"] != "ALLOW":
            return {"schema":"lom.agentic-plan/1", **route, "steps":[]}

        steps = [
            {"step":1,"operation":"LOAD_EVIDENCE","evidence_ids":list(objective.evidence_ids)},
            {"step":2,"operation":"EXECUTE_BOUNDED_TOOL","tool_id":tool["tool_id"]},
            {"step":3,"operation":"INDEPENDENT_VERIFY"},
            {"step":4,"operation":"CHECKPOINT"}
        ]
        payload = {
            "schema":"lom.agentic-plan/1",
            "decision":"ALLOW",
            "reason":"BOUNDED_PLAN_READY",
            "objective_id":objective.objective_id,
            "route_id":route["route_id"],
            "steps":steps,
        }
        return {**payload, "plan_digest":digest(payload)}

    def checkpoint(self, objective: Objective, plan: dict[str, Any], evidence_ids: Iterable[str], state: str) -> dict[str, Any]:
        ids = tuple(evidence_ids)
        if plan.get("decision") != "ALLOW" or not plan.get("plan_digest"):
            return {"decision":"HOLD","reason":"VALID_PLAN_REQUIRED"}
        if not ids:
            return {"decision":"HOLD","reason":"CHECKPOINT_EVIDENCE_REQUIRED"}
        body = {
            "schema":"lom.agentic-checkpoint/1",
            "objective_id":objective.objective_id,
            "state":state,
            "plan_digest":plan["plan_digest"],
            "evidence_ids":list(ids),
        }
        return {**body, "decision":"ALLOW", "checkpoint_digest":digest(body)}

    def verify_completion(self, checkpoint: dict[str, Any], verifier_id: str, executor_id: str, verification_evidence: Iterable[str]) -> dict[str, Any]:
        evidence = tuple(verification_evidence)
        if checkpoint.get("decision") != "ALLOW" or not checkpoint.get("checkpoint_digest"):
            return {"decision":"HOLD","reason":"VALID_CHECKPOINT_REQUIRED"}
        if not verifier_id or verifier_id == executor_id:
            return {"decision":"HOLD","reason":"INDEPENDENT_VERIFIER_REQUIRED"}
        if not evidence:
            return {"decision":"HOLD","reason":"VERIFICATION_EVIDENCE_REQUIRED"}
        result = {
            "schema":"lom.agentic-verification/1",
            "decision":"ALLOW",
            "reason":"INDEPENDENT_EVIDENCE_VERIFIED",
            "checkpoint_digest":checkpoint["checkpoint_digest"],
            "verifier_id":verifier_id,
            "evidence_ids":list(evidence),
        }
        return {**result, "verification_digest":digest(result)}

def assess_frontier_capability(*, source_official: bool, security_reviewed: bool, license_clear: bool,
                               measurable_value: bool, production_authority_required: bool) -> str:
    if not source_official or not license_clear:
        return "REJECT"
    if production_authority_required and not security_reviewed:
        return "WATCH"
    if measurable_value and security_reviewed:
        return "PILOT"
    if measurable_value:
        return "WATCH"
    return "WATCH"
