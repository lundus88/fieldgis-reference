"""Thin dispute adapter composing existing LD trust/refund controls.

Non-production. It does not replace courts, arbitration providers,
payment providers, or legal process.
"""

from __future__ import annotations
from typing import Any, Dict, Mapping

ALLOWED_STATES = {
    "OPEN",
    "EVIDENCE_GATHERING",
    "MEDIATION",
    "HUMAN_REVIEW",
    "RESOLVED",
    "APPEALED",
    "CLOSED",
}

HIGH_IMPACT_REASONS = {
    "FRAUD_ALLEGATION",
    "HIGH_VALUE_PAYMENT",
    "ACCOUNT_RESTRICTION",
    "SENSITIVE_DATA",
}

def open_dispute(case: Mapping[str, Any]) -> Dict[str, Any]:
    for field in ("dispute_id", "order_id", "opened_by", "reason_code", "evidence_ref"):
        if not case.get(field):
            return {"decision": "DENY", "reason": f"MISSING_{field.upper()}"}

    return {
        "decision": "ALLOW",
        "state": "OPEN",
        "dispute_id": case["dispute_id"],
        "order_id": case["order_id"],
        "opened_by": case["opened_by"],
        "reason_code": case["reason_code"],
        "evidence_ref": case["evidence_ref"],
        "misconduct_determined": False,
        "court_judgment": False,
        "production_authority": False,
    }

def next_step(case: Mapping[str, Any]) -> Dict[str, Any]:
    state = str(case.get("state", "")).upper()
    reason = str(case.get("reason_code", "")).upper()

    if state not in ALLOWED_STATES:
        return {"decision": "DENY", "reason": "INVALID_STATE"}

    if state == "OPEN":
        return {"decision": "ALLOW", "next_state": "EVIDENCE_GATHERING"}

    if state == "EVIDENCE_GATHERING":
        if not case.get("evidence_complete"):
            return {"decision": "HOLD", "reason": "EVIDENCE_INCOMPLETE"}
        if reason in HIGH_IMPACT_REASONS or case.get("material_value"):
            return {"decision": "ALLOW", "next_state": "HUMAN_REVIEW"}
        return {"decision": "ALLOW", "next_state": "MEDIATION"}

    if state in {"MEDIATION", "HUMAN_REVIEW"}:
        if not case.get("human_decision_ref"):
            return {"decision": "HOLD", "reason": "HUMAN_DECISION_REQUIRED"}
        return {"decision": "ALLOW", "next_state": "RESOLVED"}

    if state == "RESOLVED":
        if case.get("appeal_requested"):
            return {"decision": "ALLOW", "next_state": "APPEALED"}
        return {"decision": "ALLOW", "next_state": "CLOSED"}

    if state == "APPEALED":
        if not case.get("appeal_decision_ref"):
            return {"decision": "HOLD", "reason": "APPEAL_DECISION_REQUIRED"}
        return {"decision": "ALLOW", "next_state": "CLOSED"}

    return {"decision": "HOLD", "reason": "NO_FURTHER_AUTOMATIC_TRANSITION"}
