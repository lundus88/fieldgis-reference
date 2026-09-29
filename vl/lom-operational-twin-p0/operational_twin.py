from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

TRUTH_SCHEMA = "lom.project-state-truth/1"
FABRIC_SCHEMA = "lom.live-operational-evidence-fabric/1"

HUMAN_ONLY_ACTIONS = {
    "MERGE_PROTECTED_MAIN",
    "PRODUCTION_DEPLOY",
    "PRODUCTION_RELEASE",
    "PRODUCTION_DATA_MUTATION",
    "PRODUCTION_AUTHORITY_CHANGE",
    "FINANCIAL_COMMITMENT",
    "LEGAL_COMMITMENT",
    "PRICING_COMMITMENT",
    "CUSTOMER_COMMITMENT",
    "BID_SUBMISSION",
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _hold(reason: str, project_id: str | None = None) -> dict[str, Any]:
    body = {
        "schema": "lom.operational-twin/1",
        "status": "HOLD",
        "reason": reason,
        "project_id": project_id,
        "action_class": "HOLD",
        "next_action": "RESTORE_AUTHORITATIVE_EVIDENCE",
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }
    return {**body, "snapshot_digest": digest(body)}


def build_operational_twin(
    *,
    project_id: str,
    project_truth: dict[str, Any],
    operational_evidence: dict[str, Any],
    homeostasis: dict[str, Any],
    requested_action: str | None = None,
    production: bool = False,
    risk: str = "LOW",
    reversible: bool = True,
) -> dict[str, Any]:
    if not project_id:
        return _hold("PROJECT_ID_REQUIRED")

    if project_truth.get("schema") != TRUTH_SCHEMA:
        return _hold("PROJECT_TRUTH_SCHEMA_INVALID", project_id)
    if project_truth.get("mode") != "READ_ONLY_NON_PRODUCTION":
        return _hold("PROJECT_TRUTH_MODE_INVALID", project_id)

    truth_status = project_truth.get("status")
    if truth_status not in {"VERIFIED", "HOLD"}:
        return _hold("PROJECT_TRUTH_STATUS_UNKNOWN", project_id)
    if truth_status != "VERIFIED":
        return _hold(project_truth.get("reason") or "PROJECT_TRUTH_NOT_VERIFIED", project_id)

    if operational_evidence.get("schema") != FABRIC_SCHEMA:
        return _hold("OPERATIONAL_EVIDENCE_SCHEMA_INVALID", project_id)

    evidence_status = operational_evidence.get("status")
    if evidence_status not in {"READY", "VERIFIED"}:
        return _hold(operational_evidence.get("reason") or "OPERATIONAL_EVIDENCE_NOT_READY", project_id)

    freshness = operational_evidence.get("freshness")
    if freshness not in {"FRESH", "CURRENT"}:
        return _hold("OPERATIONAL_EVIDENCE_STALE_OR_UNKNOWN", project_id)

    body_status = homeostasis.get("status")
    if body_status not in {"HEALTHY", "DEGRADED", "HOLD", "FAILED"}:
        return _hold("HOMEOSTASIS_STATUS_UNKNOWN", project_id)
    if body_status in {"HOLD", "FAILED"}:
        return _hold("BODY_NOT_SAFE_FOR_PROGRESSION", project_id)

    if requested_action in HUMAN_ONLY_ACTIONS or production:
        action_class = "HUMAN_REVIEW"
        reason = "CONSEQUENTIAL_ACTION_REQUIRES_HUMAN"
        next_action = "PREPARE_HUMAN_DECISION_PACKAGE"
    elif risk not in {"LOW", "MEDIUM", "HIGH"}:
        return _hold("RISK_CLASS_UNKNOWN", project_id)
    elif risk == "LOW" and reversible and body_status == "HEALTHY":
        action_class = "AUTO_PREPARE"
        reason = "BOUNDED_NONPRODUCTION_PREPARATION_ELIGIBLE"
        next_action = "PREPARE_PR"
    else:
        action_class = "HUMAN_REVIEW"
        reason = "RISK_OR_REVERSIBILITY_REQUIRES_REVIEW"
        next_action = "PREPARE_HUMAN_DECISION_PACKAGE"

    body = {
        "schema": "lom.operational-twin/1",
        "status": "READY" if action_class == "AUTO_PREPARE" else "REVIEW",
        "reason": reason,
        "project_id": project_id,
        "truth_status": truth_status,
        "evidence_status": evidence_status,
        "evidence_freshness": freshness,
        "homeostasis_status": body_status,
        "requested_action": requested_action,
        "risk": risk,
        "reversible": reversible,
        "action_class": action_class,
        "next_action": next_action,
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }
    return {**body, "snapshot_digest": digest(body)}
