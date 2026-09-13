from dataclasses import dataclass

@dataclass(frozen=True)
class BusinessEvidence:
    project_id: str
    evidence_status: str
    value_signal: str
    risk: str
    urgency: str
    delivery_confidence: str


def recommend(e: BusinessEvidence) -> dict:
    if not e.project_id:
        raise ValueError("project_id required")
    if e.evidence_status in {"MISSING", "CONTRADICTORY"}:
        rec = "HOLD"
        reason = "BUSINESS_EVIDENCE_NOT_READY"
    elif e.risk in {"HIGH", "UNKNOWN"}:
        rec = "REVIEW"
        reason = "RISK_REQUIRES_HUMAN_REVIEW"
    elif e.value_signal == "HIGH" and e.urgency == "HIGH" and e.delivery_confidence in {"HIGH", "MEDIUM"}:
        rec = "PRIORITISE"
        reason = "EVIDENCE_SUPPORTED_PRIORITY"
    elif e.value_signal == "UNKNOWN" or e.delivery_confidence == "UNKNOWN":
        rec = "REVIEW"
        reason = "UNCERTAIN_BUSINESS_SIGNAL"
    else:
        rec = "MONITOR"
        reason = "NO_PRIORITY_ESCALATION"
    return {
        "project_id": e.project_id,
        "evidence_status": e.evidence_status,
        "value_signal": e.value_signal,
        "risk": e.risk,
        "urgency": e.urgency,
        "delivery_confidence": e.delivery_confidence,
        "recommendation": rec,
        "reason": reason,
        "authority": "ADVISORY_ONLY",
    }
