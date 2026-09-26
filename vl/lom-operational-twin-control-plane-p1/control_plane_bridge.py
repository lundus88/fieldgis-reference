from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterable


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _utc(ts: datetime | None = None) -> str:
    return (ts or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _exception_category(twin: dict[str, Any]) -> str:
    reason = str(twin.get("reason") or "")
    action = str(twin.get("requested_action") or "")
    if "PRODUCTION" in action or twin.get("production_authority") == "HUMAN_ONLY" and twin.get("status") == "REVIEW" and "PRODUCTION" in reason:
        return "PRODUCTION_TRANSITION"
    if any(x in reason for x in ("EVIDENCE", "TRUTH", "SCHEMA", "FRESHNESS")):
        return "EVIDENCE_GAP"
    if any(x in reason for x in ("BODY_", "HOMEOSTASIS", "BLOCKER")):
        return "UNRESOLVED_BLOCKER"
    if twin.get("action_class") == "HUMAN_REVIEW" and "CONSEQUENTIAL" in reason:
        return "HUMAN_APPROVAL"
    if twin.get("action_class") == "HUMAN_REVIEW":
        return "RISK_THRESHOLD"
    return "AUTHORITY_GAP"


def twin_to_exception(
    twin: dict[str, Any],
    *,
    created_at: str,
    evidence_refs: Iterable[str] = (),
) -> dict[str, Any] | None:
    if twin.get("schema") != "lom.operational-twin/1":
        raise ValueError("OPERATIONAL_TWIN_SCHEMA_INVALID")

    if twin.get("action_class") not in {"HOLD", "HUMAN_REVIEW"}:
        return None

    project_id = twin.get("project_id")
    if not project_id:
        raise ValueError("PROJECT_ID_REQUIRED")

    category = _exception_category(twin)
    severity = "HIGH" if twin.get("status") == "HOLD" else "MEDIUM"
    if category == "PRODUCTION_TRANSITION":
        severity = "HIGH"

    identity = {
        "project_id": project_id,
        "category": category,
        "reason": twin.get("reason"),
        "snapshot_digest": twin.get("snapshot_digest"),
    }
    exception_id = "ot-" + sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "exception_id": exception_id,
        "project_id": project_id,
        "category": category,
        "severity": severity,
        "summary": str(twin.get("reason") or "Operational Twin requires attention"),
        "decision_required": str(twin.get("next_action") or "REVIEW"),
        "recommended_action": str(twin.get("next_action") or "REVIEW"),
        "evidence_refs": sorted(set(str(x) for x in evidence_refs if x)),
        "status": "OPEN",
        "human_decision": None,
        "created_at": created_at,
        "resolved_at": None,
    }


def build_director_exception_queue(
    twins: Iterable[dict[str, Any]],
    *,
    generated_at: str | None = None,
    evidence_by_project: dict[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc()
    evidence_by_project = evidence_by_project or {}
    exceptions = []
    for twin in twins:
        item = twin_to_exception(
            twin,
            created_at=generated_at,
            evidence_refs=evidence_by_project.get(str(twin.get("project_id")), ()),
        )
        if item is not None:
            exceptions.append(item)

    exceptions.sort(key=lambda x: (x["severity"], x["project_id"], x["exception_id"]), reverse=True)
    return {
        "version": "1.0",
        "generated_at": generated_at,
        "exceptions": exceptions,
    }


def build_executive_snapshot(
    *,
    portfolio_counts: dict[str, int],
    twins: Iterable[dict[str, Any]],
    generated_at: str | None = None,
    revenue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc()
    rows = list(twins)
    queue = build_director_exception_queue(rows, generated_at=generated_at)

    total = int(portfolio_counts.get("total", len(rows)))
    portfolio = {
        "total": total,
        "healthy": int(portfolio_counts.get("healthy", 0)),
        "review": int(portfolio_counts.get("review", 0)),
        "blocked": int(portfolio_counts.get("blocked", 0)),
        "hold": int(portfolio_counts.get("hold", 0)),
        "release_candidate": int(portfolio_counts.get("release_candidate", 0)),
    }

    prepared = sum(1 for x in rows if x.get("action_class") == "AUTO_PREPARE")
    escalated = sum(1 for x in rows if x.get("action_class") in {"HOLD", "HUMAN_REVIEW"})
    verified = sum(1 for x in rows if x.get("truth_status") == "VERIFIED" and x.get("evidence_status") in {"READY", "VERIFIED"})
    denominator = prepared + escalated
    safe_rate = prepared / denominator if denominator else 0.0
    intervention_rate = escalated / denominator if denominator else 0.0

    top_priorities = [
        {
            "project_id": str(x.get("project_id")),
            "reason": str(x.get("reason") or "Operational Twin attention required"),
        }
        for x in rows
        if x.get("action_class") in {"HOLD", "HUMAN_REVIEW"}
    ]

    snapshot = {
        "generated_at": generated_at,
        "portfolio": portfolio,
        "autonomy": {
            "tasks_executed": 0,
            "tasks_verified": verified,
            "tasks_escalated": escalated,
            "safe_autonomous_completion_rate": safe_rate,
            "director_intervention_rate": intervention_rate,
        },
        "director_queue": {
            "open_count": len(queue["exceptions"]),
            "critical_count": sum(x["severity"] == "CRITICAL" for x in queue["exceptions"]),
            "top_exception_ids": [x["exception_id"] for x in queue["exceptions"][:5]],
        },
        "top_priorities": top_priorities[:10],
    }
    if revenue is not None:
        snapshot["revenue"] = revenue
    return snapshot
