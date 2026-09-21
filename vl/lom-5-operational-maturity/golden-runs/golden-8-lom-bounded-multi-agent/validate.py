from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXEC = json.loads((HERE / "execution-result.json").read_text(encoding="utf-8"))
OUT = HERE / "independent-validation.json"


def main() -> int:
    errors: list[str] = []

    if EXEC.get("schema") != "lom.golden-workflow-execution/2":
        errors.append("INVALID_EXECUTION_SCHEMA")
    if EXEC.get("final_outcome") != "PASS":
        errors.append("OUTCOME_NOT_PASS")

    delegation = EXEC.get("multi_agent_delegation")
    if not isinstance(delegation, dict):
        errors.append("MULTI_AGENT_DELEGATION_REQUIRED")
    else:
        if delegation.get("demonstrated") is not True:
            errors.append("DELEGATION_NOT_DEMONSTRATED")
        if delegation.get("authority_expanded") is not False:
            errors.append("AUTHORITY_EXPANSION_DETECTED")
        if delegation.get("worker_count") != 4:
            errors.append("WORKER_COUNT_UNEXPECTED")
        if delegation.get("executor_actor_id") == delegation.get("validator_actor_id"):
            errors.append("EXECUTOR_VALIDATOR_COLLISION")
        if delegation.get("production_approval") != "HUMAN_ONLY":
            errors.append("PRODUCTION_AUTHORITY_DRIFT")
        if delegation.get("production_locked") is not True:
            errors.append("PRODUCTION_LOCK_REQUIRED")

    positive = EXEC.get("positive_checks")
    negative = EXEC.get("negative_checks")
    if not isinstance(positive, dict) or not positive or not all(positive.values()):
        errors.append("POSITIVE_DELEGATION_CHECK_FAILED")
    if not isinstance(negative, dict) or not negative or not all(negative.values()):
        errors.append("NEGATIVE_BOUNDARY_CHECK_FAILED")

    required_denials = {
        "forbidden_capability": ("DENY", "FORBIDDEN_CAPABILITY_REQUESTED"),
        "widened_budget": ("DENY", "BUDGET_EXPANSION_BLOCKED"),
        "widened_scope": ("DENY", "RESOURCE_SCOPE_EXPANSION_BLOCKED"),
    }
    denial = EXEC.get("denial_evidence") or {}
    for key, expected in required_denials.items():
        item = denial.get(key) or {}
        if (item.get("decision"), item.get("reason")) != expected:
            errors.append(f"INVALID_DENIAL_{key.upper()}")

    swarm = denial.get("swarm_mode") or {}
    if (
        swarm.get("status") != "BLOCKED"
        or swarm.get("reason") != "SWARM_MODE_FORBIDDEN_BY_DEFAULT"
    ):
        errors.append("SWARM_MODE_NOT_BLOCKED")

    collision = denial.get("actor_collision") or {}
    if (
        collision.get("decision") != "HOLD"
        or collision.get("reason") != "EXECUTOR_VALIDATOR_COLLISION"
    ):
        errors.append("ACTOR_COLLISION_NOT_BLOCKED")

    safety_widening = denial.get("safety_capability_widening") or {}
    if (
        safety_widening.get("decision") != "HOLD"
        or safety_widening.get("reason") != "DELEGATION_CAPABILITY_WIDENED"
    ):
        errors.append("SAFETY_WIDENING_NOT_BLOCKED")

    if EXEC.get("model_or_external_api_calls") != 0:
        errors.append("UNEXPECTED_EXTERNAL_API_CALL")
    if EXEC.get("external_network_calls") != 0:
        errors.append("UNEXPECTED_EXTERNAL_NETWORK_CALL")
    if EXEC.get("estimated_model_tool_cost") != 0.0:
        errors.append("UNEXPECTED_MODEL_TOOL_COST")

    for key in (
        "budget_overrun",
        "authority_expansion_incident",
        "fabricated_pass_incident",
        "production_approval",
        "builder_self_certified",
    ):
        if EXEC.get(key) is not False:
            errors.append(f"INVALID_{key.upper()}")

    result = {
        "schema": "lom.independent-validation/2",
        "validator_role": "INDEPENDENT_VALIDATOR",
        "status": "PASS" if not errors else "HOLD",
        "errors": sorted(errors),
        "source_github_sha": EXEC.get("github_sha"),
        "source_github_run_id": EXEC.get("github_run_id"),
        "expected_terminal_outcome": "PASS",
        "bounded_multi_agent_expected": True,
        "builder_self_certification": False,
        "production_authority": "HUMAN_ONLY",
    }

    OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
