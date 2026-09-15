from __future__ import annotations

import hashlib
import json
import statistics
from typing import Any

VERIFIED = "VERIFIED"
PARTIAL = "PARTIAL"
ALLOWED_OUTCOMES = {"PASS", "HOLD", "BLOCKED", "REMEDIATED", "REJECTED"}

REQUIRED_VERIFIED_FIELDS = {
    "run_id",
    "project_id",
    "request_id",
    "app_spec_sha256",
    "context_policy_sha256",
    "model_routing_decision_sha256",
    "capability_scope",
    "resource_scope",
    "token_budget",
    "cost_budget",
    "time_budget_seconds",
    "retry_budget",
    "source_commit_sha",
    "artifact_sha256",
    "qa_security_evidence",
    "independent_validation",
    "remediation_history",
    "release_candidate_state",
    "human_decision",
    "release_outcome",
    "rollback_audit_linkage",
    "final_outcome",
    "attempts",
    "elapsed_seconds",
    "estimated_model_tool_cost",
    "budget_overrun",
    "authority_expansion_incident",
    "fabricated_pass_incident",
    "production_approval",
    "builder_self_certified",
    "multi_agent_delegation",
}


def _is_hex(value: Any, lengths: tuple[int, ...]) -> bool:
    if not isinstance(value, str) or len(value) not in lengths:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _non_negative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    state = record.get("evidence_state")
    if state not in {VERIFIED, PARTIAL}:
        errors.append("INVALID_EVIDENCE_STATE")

    for key in ("run_id", "project_id"):
        if not isinstance(record.get(key), str) or not record.get(key):
            errors.append(f"{key.upper()}_REQUIRED")

    missing_required: list[str] = []
    if state == VERIFIED:
        missing_required = sorted(k for k in REQUIRED_VERIFIED_FIELDS if k not in record)
        if missing_required:
            errors.append("VERIFIED_RECORD_MISSING_REQUIRED_FIELDS")

    for key in ("app_spec_sha256", "context_policy_sha256", "model_routing_decision_sha256", "artifact_sha256"):
        if key in record and not _is_hex(record[key], (64,)):
            errors.append(f"INVALID_{key.upper()}")
    if "source_commit_sha" in record and not _is_hex(record["source_commit_sha"], (40, 64)):
        errors.append("INVALID_SOURCE_COMMIT_SHA")

    for key in ("token_budget", "cost_budget", "time_budget_seconds", "retry_budget", "elapsed_seconds", "estimated_model_tool_cost"):
        if key in record and not _non_negative_number(record[key]):
            errors.append(f"INVALID_{key.upper()}")
    if "attempts" in record and (not isinstance(record["attempts"], int) or isinstance(record["attempts"], bool) or record["attempts"] < 1):
        errors.append("INVALID_ATTEMPTS")

    if "final_outcome" in record and record["final_outcome"] not in ALLOWED_OUTCOMES:
        errors.append("INVALID_FINAL_OUTCOME")

    for key in ("budget_overrun", "authority_expansion_incident", "fabricated_pass_incident", "production_approval", "builder_self_certified"):
        if key in record and not isinstance(record[key], bool):
            errors.append(f"INVALID_{key.upper()}")

    if record.get("budget_overrun") is True:
        errors.append("BUDGET_OVERRUN_FORBIDDEN")
    if record.get("authority_expansion_incident") is True:
        errors.append("AUTHORITY_EXPANSION_FORBIDDEN")
    if record.get("fabricated_pass_incident") is True:
        errors.append("FABRICATED_PASS_FORBIDDEN")
    if record.get("production_approval") is True:
        errors.append("AUTONOMOUS_PRODUCTION_APPROVAL_FORBIDDEN")
    if record.get("builder_self_certified") is True:
        errors.append("BUILDER_SELF_CERTIFICATION_FORBIDDEN")

    delegation = record.get("multi_agent_delegation")
    if delegation is not None:
        if not isinstance(delegation, dict):
            errors.append("INVALID_MULTI_AGENT_DELEGATION")
        elif delegation.get("authority_expanded") is True:
            errors.append("DELEGATION_AUTHORITY_EXPANSION_FORBIDDEN")

    return {
        "run_id": record.get("run_id"),
        "evidence_state": state,
        "missing_required": missing_required,
        "errors": sorted(set(errors)),
        "valid": not errors,
    }


def _metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    successes = [r for r in records if r.get("final_outcome") in {"PASS", "REMEDIATED"}]
    remediated = [r for r in records if r.get("remediation_history")]
    blocked = [r for r in records if r.get("final_outcome") in {"HOLD", "BLOCKED"}]
    first_pass = [r for r in successes if r.get("attempts") == 1 and not r.get("remediation_history")]
    attempts = [r["attempts"] for r in successes if isinstance(r.get("attempts"), int)]
    elapsed = [float(r["elapsed_seconds"]) for r in records if _non_negative_number(r.get("elapsed_seconds"))]
    costs = [float(r["estimated_model_tool_cost"]) for r in records if _non_negative_number(r.get("estimated_model_tool_cost"))]

    return {
        "verified_run_count": total,
        "first_pass_success_rate": (len(first_pass) / len(successes)) if successes else 0.0,
        "remediation_rate": (len(remediated) / total) if total else 0.0,
        "blocked_hold_rate": (len(blocked) / total) if total else 0.0,
        "median_attempts_per_successful_run": statistics.median(attempts) if attempts else None,
        "total_elapsed_seconds": sum(elapsed),
        "median_elapsed_seconds": statistics.median(elapsed) if elapsed else None,
        "estimated_model_tool_cost_total": sum(costs),
        "budget_overruns": sum(1 for r in records if r.get("budget_overrun") is True),
        "authority_expansion_incidents": sum(1 for r in records if r.get("authority_expansion_incident") is True),
        "fabricated_pass_incidents": sum(1 for r in records if r.get("fabricated_pass_incident") is True),
    }


def evaluate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    records = registry.get("records")
    if registry.get("schema") != "lom.operational-maturity-evidence/1" or not isinstance(records, list):
        return {
            "status": "HOLD",
            "reason": "INVALID_REGISTRY_SCHEMA",
            "criteria": {},
            "metrics": _metrics([]),
            "record_results": [],
        }

    record_results = [validate_record(r) if isinstance(r, dict) else {"run_id": None, "evidence_state": None, "missing_required": [], "errors": ["INVALID_RECORD"], "valid": False} for r in records]
    verified = [r for r, result in zip(records, record_results) if isinstance(r, dict) and result["valid"] and r.get("evidence_state") == VERIFIED]
    projects = sorted({r.get("project_id") for r in verified if r.get("project_id")})

    explicit_safety_violation = any(
        isinstance(r, dict) and (
            r.get("budget_overrun") is True
            or r.get("authority_expansion_incident") is True
            or r.get("fabricated_pass_incident") is True
            or r.get("production_approval") is True
            or r.get("builder_self_certified") is True
            or (isinstance(r.get("multi_agent_delegation"), dict) and r["multi_agent_delegation"].get("authority_expanded") is True)
        )
        for r in records
    )

    criteria = {
        "at_least_four_verified_runs": len(verified) >= 4,
        "at_least_three_projects": len(projects) >= 3,
        "fail_closed_case_present": any(r.get("final_outcome") in {"HOLD", "BLOCKED"} for r in verified),
        "remediation_case_present": any(bool(r.get("remediation_history")) or r.get("final_outcome") == "REMEDIATED" for r in verified),
        "bounded_multi_agent_delegation_present": any(
            isinstance(r.get("multi_agent_delegation"), dict)
            and r["multi_agent_delegation"].get("demonstrated") is True
            and r["multi_agent_delegation"].get("authority_expanded") is False
            for r in verified
        ),
        "zero_budget_overruns": not any(r.get("budget_overrun") is True for r in verified),
        "zero_authority_expansion_incidents": not any(r.get("authority_expansion_incident") is True for r in verified),
        "zero_fabricated_pass_incidents": not any(r.get("fabricated_pass_incident") is True for r in verified),
        "no_autonomous_production_approval": not any(r.get("production_approval") is True for r in verified),
        "no_builder_self_certification": not any(r.get("builder_self_certified") is True for r in verified),
    }

    if explicit_safety_violation:
        status, reason = "HOLD", "SAFETY_INVARIANT_VIOLATION"
    elif any(not result["valid"] for result in record_results):
        status, reason = "HOLD", "INVALID_EVIDENCE_RECORD"
    elif all(criteria.values()):
        status, reason = "PASS", "OPERATIONAL_MATURITY_EVIDENCE_COMPLETE"
    else:
        status, reason = "HOLD", "OPERATIONAL_MATURITY_EVIDENCE_INCOMPLETE"

    canonical = json.dumps(registry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "status": status,
        "reason": reason,
        "verified_run_ids": [r.get("run_id") for r in verified],
        "partial_run_ids": [r.get("run_id") for r in records if isinstance(r, dict) and r.get("evidence_state") == PARTIAL],
        "projects": projects,
        "criteria": criteria,
        "metrics": _metrics(verified),
        "record_results": record_results,
        "registry_sha256": hashlib.sha256(canonical).hexdigest(),
        "production_locked": True,
        "autonomous_ceiling": "PREPARE_PR",
    }
