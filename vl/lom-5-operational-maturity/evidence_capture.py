from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from multi_project_evidence import validate_record

CAPTURE_SCHEMA = "lom.golden-workflow-evidence-capture/2"
AUTONOMOUS_CEILING = "PREPARE_PR"


def sha256_json(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def begin_capture(
    *,
    run_id: str,
    project_id: str,
    request_id: str,
    app_spec: dict[str, Any],
    context_policy: dict[str, Any],
    model_routing_decision: dict[str, Any],
    capability_scope: list[str],
    resource_scope: list[str],
    token_budget: int | float,
    cost_budget: int | float,
    time_budget_seconds: int | float,
    retry_budget: int,
    source_commit_sha: str,
) -> dict[str, Any]:
    if not all(isinstance(v, str) and v for v in (run_id, project_id, request_id)):
        raise ValueError("RUN_PROJECT_REQUEST_ID_REQUIRED")
    if not isinstance(capability_scope, list) or not capability_scope:
        raise ValueError("CAPABILITY_SCOPE_REQUIRED")
    if not isinstance(resource_scope, list) or not resource_scope:
        raise ValueError("RESOURCE_SCOPE_REQUIRED")
    for name, value in (
        ("token_budget", token_budget),
        ("cost_budget", cost_budget),
        ("time_budget_seconds", time_budget_seconds),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"INVALID_{name.upper()}")
    if (
        not isinstance(retry_budget, int)
        or isinstance(retry_budget, bool)
        or retry_budget < 0
    ):
        raise ValueError("INVALID_RETRY_BUDGET")
    if not isinstance(source_commit_sha, str) or len(source_commit_sha) not in {40, 64}:
        raise ValueError("INVALID_SOURCE_COMMIT_SHA")

    return {
        "capture_schema": CAPTURE_SCHEMA,
        "run_id": run_id,
        "project_id": project_id,
        "request_id": request_id,
        "app_spec_sha256": sha256_json(app_spec),
        "context_policy_sha256": sha256_json(context_policy),
        "model_routing_decision_sha256": sha256_json(model_routing_decision),
        "capability_scope": deepcopy(capability_scope),
        "resource_scope": deepcopy(resource_scope),
        "token_budget": token_budget,
        "cost_budget": cost_budget,
        "time_budget_seconds": time_budget_seconds,
        "retry_budget": retry_budget,
        "source_commit_sha": source_commit_sha,
        "authority": {
            "autonomous_ceiling": AUTONOMOUS_CEILING,
            "production_approval": "HUMAN_ONLY",
            "protected_main_merge": "HUMAN_ONLY",
            "self_certification": "FORBIDDEN",
        },
    }


def finalize_capture(
    envelope: dict[str, Any],
    *,
    artifact_bytes: bytes,
    qa_security_evidence: list[dict[str, Any]],
    independent_validation: dict[str, Any] | None,
    remediation_history: list[dict[str, Any]],
    release_candidate_state: str,
    human_decision: str | None,
    release_outcome: str,
    rollback_audit_linkage: str,
    final_outcome: str,
    attempts: int,
    elapsed_seconds: int | float,
    estimated_model_tool_cost: int | float,
    production_approval: bool = False,
    builder_self_certified: bool = False,
    authority_expansion_incident: bool = False,
    fabricated_pass_incident: bool = False,
    multi_agent_delegation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if envelope.get("capture_schema") != CAPTURE_SCHEMA:
        raise ValueError("INVALID_CAPTURE_SCHEMA")

    budget_overrun = (
        attempts > int(envelope["retry_budget"]) + 1
        or elapsed_seconds > envelope["time_budget_seconds"]
        or estimated_model_tool_cost > envelope["cost_budget"]
    )

    record = {
        "run_id": envelope["run_id"],
        "project_id": envelope["project_id"],
        "evidence_state": "VERIFIED",
        "request_id": envelope["request_id"],
        "app_spec_sha256": envelope["app_spec_sha256"],
        "context_policy_sha256": envelope["context_policy_sha256"],
        "model_routing_decision_sha256": envelope[
            "model_routing_decision_sha256"
        ],
        "capability_scope": deepcopy(envelope["capability_scope"]),
        "resource_scope": deepcopy(envelope["resource_scope"]),
        "token_budget": envelope["token_budget"],
        "cost_budget": envelope["cost_budget"],
        "time_budget_seconds": envelope["time_budget_seconds"],
        "retry_budget": envelope["retry_budget"],
        "source_commit_sha": envelope["source_commit_sha"],
        "artifact_sha256": sha256_bytes(artifact_bytes),
        "qa_security_evidence": deepcopy(qa_security_evidence),
        "independent_validation": deepcopy(independent_validation),
        "remediation_history": deepcopy(remediation_history),
        "release_candidate_state": release_candidate_state,
        "human_decision": human_decision,
        "release_outcome": release_outcome,
        "rollback_audit_linkage": rollback_audit_linkage,
        "final_outcome": final_outcome,
        "attempts": attempts,
        "elapsed_seconds": elapsed_seconds,
        "estimated_model_tool_cost": estimated_model_tool_cost,
        "budget_overrun": budget_overrun,
        "authority_expansion_incident": authority_expansion_incident,
        "fabricated_pass_incident": fabricated_pass_incident,
        "production_approval": production_approval,
        "builder_self_certified": builder_self_certified,
        "multi_agent_delegation": (
            deepcopy(multi_agent_delegation)
            if multi_agent_delegation is not None
            else {"demonstrated": False, "authority_expanded": False}
        ),
    }

    capture_errors: list[str] = []
    if not isinstance(independent_validation, dict) or not independent_validation:
        capture_errors.append("INDEPENDENT_VALIDATION_REQUIRED")
    if not isinstance(human_decision, str) or not human_decision:
        capture_errors.append("HUMAN_DECISION_REQUIRED")
    if not isinstance(qa_security_evidence, list) or not qa_security_evidence:
        capture_errors.append("QA_SECURITY_EVIDENCE_REQUIRED")
    if not isinstance(remediation_history, list):
        capture_errors.append("REMEDIATION_HISTORY_LIST_REQUIRED")
    if not isinstance(artifact_bytes, (bytes, bytearray)) or not artifact_bytes:
        capture_errors.append("ARTIFACT_REQUIRED")

    result = validate_record(record)
    capture_errors.extend(result["errors"])

    if capture_errors:
        record["evidence_state"] = "PARTIAL"
        record["capture_errors"] = sorted(set(capture_errors))
        record["promotion_allowed"] = False
    else:
        record["capture_errors"] = []
        record["promotion_allowed"] = True

    record["autonomous_ceiling"] = AUTONOMOUS_CEILING
    record["production_locked"] = True
    return record
