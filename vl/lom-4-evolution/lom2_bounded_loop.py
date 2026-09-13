from __future__ import annotations

HUMAN_ONLY_ACTIONS = {
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_DEPLOY",
    "PRODUCTION_RELEASE",
    "PRODUCTION_DATA_MUTATION",
    "WIDEN_AUTHORITY",
    "CUSTOMER_OUTREACH",
    "BID_SUBMISSION",
    "QUOTATION_OR_PRICING_COMMITMENT",
    "CONTRACT_OR_LEGAL_COMMITMENT",
    "FINANCIAL_COMMITMENT",
}

ROLE_ORDER = ("PLANNER", "RISK_GOVERNOR", "EXECUTOR", "VALIDATOR", "MEMORY_KEEPER")


def _unique(items):
    return list(dict.fromkeys(items))


def build_plan(goal: dict) -> dict:
    allowed = set(goal.get("delegation", {}).get("allowed_actions", []))
    forbidden = set(goal.get("delegation", {}).get("forbidden_actions", []))
    requested = set(goal.get("requested_actions", []))
    evidence_required = goal.get("evidence_required", [])

    blocked = sorted((requested & HUMAN_ONLY_ACTIONS) | (requested & forbidden))
    executable = sorted((requested & allowed) - HUMAN_ONLY_ACTIONS - forbidden)
    unknown = sorted(requested - allowed - forbidden - HUMAN_ONLY_ACTIONS)

    status = "READY"
    reasons = []
    if not goal.get("objective") or not goal.get("success_criteria") or not evidence_required:
        status = "HOLD"
        reasons.append("GOAL_CONTRACT_INCOMPLETE")
    if goal.get("risk_class") == "HUMAN_ONLY" or blocked:
        status = "ESCALATE"
        reasons.append("HUMAN_ONLY_BOUNDARY")
    if unknown:
        status = "HOLD"
        reasons.append("UNKNOWN_AUTHORITY")

    tasks = [
        {"id": "plan", "role": "PLANNER", "action": "DRAFT_PLAN", "depends_on": []},
        {"id": "risk", "role": "RISK_GOVERNOR", "action": "CLASSIFY_RISK", "depends_on": ["plan"]},
    ]
    for i, action in enumerate(executable, 1):
        tasks.append({"id": f"exec-{i}", "role": "EXECUTOR", "action": action, "depends_on": ["risk"]})
    execution_ids = [t["id"] for t in tasks if t["role"] == "EXECUTOR"]
    tasks.append({"id": "validate", "role": "VALIDATOR", "action": "VALIDATE", "depends_on": execution_ids or ["risk"]})
    tasks.append({"id": "learn", "role": "MEMORY_KEEPER", "action": "RECORD_OUTCOME", "depends_on": ["validate"]})

    return {
        "goal_id": goal.get("goal_id"),
        "status": status,
        "reasons": _unique(reasons),
        "executable_actions": executable,
        "blocked_actions": blocked,
        "unknown_actions": unknown,
        "tasks": tasks,
        "requires_human": status == "ESCALATE",
    }


def validate_execution(plan: dict, execution: dict) -> dict:
    actor_role = execution.get("actor_role")
    action = execution.get("action")
    evidence = execution.get("evidence", [])

    if actor_role != "EXECUTOR":
        return {"verdict": "HOLD", "reason": "INVALID_EXECUTOR_ROLE"}
    if action in HUMAN_ONLY_ACTIONS:
        return {"verdict": "HOLD", "reason": "HUMAN_ONLY_BOUNDARY"}
    if action not in plan.get("executable_actions", []):
        return {"verdict": "HOLD", "reason": "ACTION_OUTSIDE_DELEGATION"}
    if not evidence:
        return {"verdict": "HOLD", "reason": "MISSING_EXECUTION_EVIDENCE"}
    return {"verdict": "READY_FOR_INDEPENDENT_VALIDATION", "reason": "BOUNDED_EXECUTION_RECORDED"}


def independent_validate(plan: dict, execution_result: dict, validator_role: str) -> dict:
    if validator_role != "VALIDATOR":
        return {"verdict": "HOLD", "reason": "INDEPENDENCE_REQUIRED"}
    if execution_result.get("actor_role") == validator_role:
        return {"verdict": "HOLD", "reason": "SELF_CERTIFICATION_FORBIDDEN"}
    preliminary = validate_execution(plan, execution_result)
    if preliminary["verdict"] != "READY_FOR_INDEPENDENT_VALIDATION":
        return preliminary
    return {"verdict": "PASS", "reason": "INDEPENDENT_VALIDATION_COMPLETE"}
