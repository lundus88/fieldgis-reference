from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

HUMAN_ONLY_STATES = {"ESCALATE"}
CONTROL_ACTIONS = {"PAUSE", "QUARANTINE", "STOP"}
NON_PRODUCTION_ENVIRONMENTS = {"DEVELOPMENT", "NON_PRODUCTION", "STAGING", "SANDBOX"}


@dataclass(frozen=True)
class MissionInput:
    objective_id: str
    lifecycle_state: str
    evidence_status: str
    risk_state: str
    agent_states: tuple
    exceptions: tuple = ()


@dataclass(frozen=True)
class OperationalTelemetry:
    objective_id: str
    project_id: str
    golden_workflow_id: str | None = None
    evidence_gap_count: int = 0
    incident_count: int = 0
    critical_incident_count: int = 0
    pending_approvals: int = 0
    estimated_cost_usd: float = 0.0
    cost_budget_usd: float | None = None
    elapsed_ms: int = 0
    time_budget_ms: int | None = None
    retry_count: int = 0
    retry_budget: int | None = None
    slo_breached: bool = False
    source_reference: str | None = None
    evidence_fresh: bool = True


@dataclass(frozen=True)
class ControlIntent:
    objective_id: str
    action: str
    environment: str
    requested_by: str
    evidence_status: str
    source_reference: str | None
    evidence_fresh: bool = True
    reversible: bool = True


def build_snapshot(data: MissionInput) -> dict:
    """Build the original Mission Control objective snapshot.

    This function intentionally preserves the v1 output contract so existing
    consumers remain compatible while v2 portfolio/control features are added
    through separate additive functions below.
    """
    if not data.objective_id:
        raise ValueError("objective_id required")
    action = "NONE"
    state = data.lifecycle_state
    exceptions = list(data.exceptions)

    if data.evidence_status in {"MISSING", "CONTRADICTORY"}:
        state = "HOLD"
        action = "ACQUIRE_EVIDENCE"
        exceptions.append("EVIDENCE_NOT_READY")
    elif data.risk_state in {"HIGH", "UNKNOWN"}:
        state = "ESCALATE"
        action = "APPROVE_OR_REJECT"
        exceptions.append("RISK_REQUIRES_DIRECTOR")
    elif data.lifecycle_state in HUMAN_ONLY_STATES:
        action = "APPROVE_OR_REJECT"
    elif data.lifecycle_state == "HOLD":
        action = "REVIEW"

    return {
        "objective_id": data.objective_id,
        "lifecycle_state": state,
        "evidence_status": data.evidence_status,
        "risk_state": data.risk_state,
        "agent_states": [{"role": r, "state": s} for r, s in data.agent_states],
        "exceptions": exceptions,
        "recommended_director_action": action,
    }


def _valid_nonnegative_int(value: int | None) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_nonnegative_number(value: float | int | None) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def classify_telemetry(data: OperationalTelemetry) -> dict:
    """Classify one objective/project telemetry record fail-closed."""
    if not data.objective_id or not data.project_id:
        return {"action_class": "HOLD", "reason": "OBJECTIVE_AND_PROJECT_REQUIRED"}
    if not data.evidence_fresh:
        return {"action_class": "HOLD", "reason": "TELEMETRY_EVIDENCE_STALE"}
    if not data.source_reference:
        return {"action_class": "HOLD", "reason": "TELEMETRY_PROVENANCE_REQUIRED"}

    integer_fields = (
        data.evidence_gap_count,
        data.incident_count,
        data.critical_incident_count,
        data.pending_approvals,
        data.elapsed_ms,
        data.retry_count,
    )
    if not all(_valid_nonnegative_int(value) for value in integer_fields):
        return {"action_class": "HOLD", "reason": "INVALID_TELEMETRY_COUNTER"}
    if data.critical_incident_count > data.incident_count:
        return {"action_class": "HOLD", "reason": "INCIDENT_COUNT_CONTRADICTION"}

    if not _valid_nonnegative_number(data.estimated_cost_usd):
        return {"action_class": "HOLD", "reason": "INVALID_COST_MEASUREMENT"}
    if data.cost_budget_usd is not None:
        if not _valid_nonnegative_number(data.cost_budget_usd):
            return {"action_class": "HOLD", "reason": "INVALID_COST_BUDGET"}
        if data.estimated_cost_usd > data.cost_budget_usd:
            return {"action_class": "HOLD", "reason": "COST_BUDGET_EXCEEDED"}

    if data.time_budget_ms is not None:
        if not _valid_nonnegative_int(data.time_budget_ms):
            return {"action_class": "HOLD", "reason": "INVALID_TIME_BUDGET"}
        if data.elapsed_ms > data.time_budget_ms:
            return {"action_class": "HOLD", "reason": "TIME_BUDGET_EXCEEDED"}

    if data.retry_budget is not None:
        if not _valid_nonnegative_int(data.retry_budget):
            return {"action_class": "HOLD", "reason": "INVALID_RETRY_BUDGET"}
        if data.retry_count > data.retry_budget:
            return {"action_class": "HOLD", "reason": "RETRY_BUDGET_EXCEEDED"}

    if data.evidence_gap_count > 0:
        return {"action_class": "HOLD", "reason": "EVIDENCE_GAPS_PRESENT"}
    if data.critical_incident_count > 0:
        return {"action_class": "HUMAN_REVIEW", "reason": "CRITICAL_INCIDENT_PRESENT"}
    if data.pending_approvals > 0:
        return {"action_class": "HUMAN_REVIEW", "reason": "HUMAN_APPROVAL_PENDING"}
    if data.slo_breached:
        return {"action_class": "HUMAN_REVIEW", "reason": "SLO_BREACH"}

    return {"action_class": "MONITOR", "reason": "TELEMETRY_WITHIN_BOUNDS"}


def telemetry_card(data: OperationalTelemetry) -> dict:
    decision = classify_telemetry(data)
    return {
        "objective_id": data.objective_id,
        "project_id": data.project_id,
        "golden_workflow_id": data.golden_workflow_id,
        "action_class": decision["action_class"],
        "reason": decision["reason"],
        "evidence_gap_count": data.evidence_gap_count,
        "incident_count": data.incident_count,
        "critical_incident_count": data.critical_incident_count,
        "pending_approvals": data.pending_approvals,
        "estimated_cost_usd": data.estimated_cost_usd,
        "cost_budget_usd": data.cost_budget_usd,
        "elapsed_ms": data.elapsed_ms,
        "time_budget_ms": data.time_budget_ms,
        "retry_count": data.retry_count,
        "retry_budget": data.retry_budget,
        "slo_breached": data.slo_breached,
        "source_reference": data.source_reference,
        "evidence_fresh": data.evidence_fresh,
    }


def evaluate_control_intent(intent: ControlIntent) -> dict:
    """Evaluate a director control request without executing it.

    Mission Control v2 prepares governed control intent only. It never executes
    STOP/PAUSE/QUARANTINE and never gains Production authority.
    """
    if not intent.objective_id:
        return _control_decision("HOLD", "OBJECTIVE_ID_REQUIRED")
    if intent.action not in CONTROL_ACTIONS:
        return _control_decision("HOLD", "UNKNOWN_CONTROL_ACTION")
    if not intent.requested_by:
        return _control_decision("HOLD", "CONTROL_REQUESTOR_REQUIRED")
    if not intent.evidence_fresh:
        return _control_decision("HOLD", "CONTROL_EVIDENCE_STALE")
    if not intent.source_reference:
        return _control_decision("HOLD", "CONTROL_PROVENANCE_REQUIRED")
    if intent.evidence_status != "COMPLETE":
        return _control_decision("HOLD", "CONTROL_EVIDENCE_INCOMPLETE")
    if intent.environment == "PRODUCTION":
        return _control_decision("HUMAN_REVIEW", "PRODUCTION_CONTROL_HUMAN_ONLY")
    if intent.environment not in NON_PRODUCTION_ENVIRONMENTS:
        return _control_decision("HOLD", "UNKNOWN_CONTROL_ENVIRONMENT")
    if intent.action == "STOP":
        return _control_decision("HUMAN_REVIEW", "STOP_REQUIRES_HUMAN_DECISION")
    if not intent.reversible:
        return _control_decision("HUMAN_REVIEW", "IRREVERSIBLE_CONTROL_REQUIRES_HUMAN")
    return _control_decision("PREPARE_CONTROL", "BOUNDED_NONPROD_CONTROL_INTENT")


def _control_decision(status: str, reason: str) -> dict:
    return {
        "status": status,
        "reason": reason,
        "execution_authority": "NONE",
        "execution_performed": False,
        "production_authority": "HUMAN_ONLY",
    }


def build_mission_control_view(
    missions: Iterable[MissionInput],
    telemetry: Iterable[OperationalTelemetry] = (),
    control_intents: Iterable[ControlIntent] = (),
) -> dict:
    """Compose the Director Mission Control v2 portfolio view."""
    objectives = [build_snapshot(item) for item in missions]
    telemetry_cards = [telemetry_card(item) for item in telemetry]
    controls = [
        {
            "objective_id": item.objective_id,
            "action": item.action,
            "environment": item.environment,
            **evaluate_control_intent(item),
        }
        for item in control_intents
    ]

    evidence_gap_total = sum(card["evidence_gap_count"] for card in telemetry_cards)
    incident_total = sum(card["incident_count"] for card in telemetry_cards)
    critical_incident_total = sum(card["critical_incident_count"] for card in telemetry_cards)
    pending_approval_total = sum(card["pending_approvals"] for card in telemetry_cards)
    estimated_cost_total_usd = round(sum(float(card["estimated_cost_usd"]) for card in telemetry_cards), 6)

    budget_overrun_count = sum(
        1
        for card in telemetry_cards
        if card["cost_budget_usd"] is not None
        and card["estimated_cost_usd"] > card["cost_budget_usd"]
    )
    slo_breach_count = sum(1 for card in telemetry_cards if card["slo_breached"])

    action_classes = [card["action_class"] for card in telemetry_cards]
    if any(item["lifecycle_state"] == "HOLD" for item in objectives) or "HOLD" in action_classes:
        overall = "HOLD"
    elif any(item["lifecycle_state"] == "ESCALATE" for item in objectives) or "HUMAN_REVIEW" in action_classes:
        overall = "HUMAN_REVIEW"
    elif any(item["status"] == "HUMAN_REVIEW" for item in controls):
        overall = "HUMAN_REVIEW"
    elif controls and any(item["status"] == "HOLD" for item in controls):
        overall = "HOLD"
    else:
        overall = "MONITOR"

    return {
        "schema_version": 2,
        "mode": "READ_ONLY_NON_PRODUCTION",
        "overall_action_class": overall,
        "objectives": objectives,
        "telemetry": telemetry_cards,
        "control_intents": controls,
        "portfolio": {
            "objective_count": len(objectives),
            "telemetry_record_count": len(telemetry_cards),
            "evidence_gap_total": evidence_gap_total,
            "incident_total": incident_total,
            "critical_incident_total": critical_incident_total,
            "pending_approval_total": pending_approval_total,
            "budget_overrun_count": budget_overrun_count,
            "slo_breach_count": slo_breach_count,
            "estimated_cost_total_usd": estimated_cost_total_usd,
        },
        "autonomous_ceiling": "PREPARE_PR",
        "control_execution": "DISABLED",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }
