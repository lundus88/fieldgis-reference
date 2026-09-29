"""Evidence-backed skill signal adapter for LOM Digital Nation.

This is a thin Preview adapter, not a second LMS.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


VERIFIED_METHODS = {
    "ASSESSMENT",
    "HUMAN_REVIEW",
    "SIGNED_PROVIDER_ASSERTION",
    "DETERMINISTIC_RULE",
}


def normalize_skill_signal(signal: Mapping[str, Any]) -> Dict[str, Any]:
    status = str(signal.get("status", "SELF_REPORTED")).upper()
    method = str(signal.get("verification_method", "SELF_REPORT")).upper()
    evidence_ref = signal.get("evidence_ref")

    if status == "VERIFIED":
        if method not in VERIFIED_METHODS:
            return {
                "decision": "DENY",
                "reason": "UNSUPPORTED_VERIFICATION_METHOD",
                "verified": False,
            }
        if not evidence_ref:
            return {
                "decision": "DENY",
                "reason": "MISSING_VERIFICATION_EVIDENCE",
                "verified": False,
            }

    if method == "SELF_REPORT" and status == "VERIFIED":
        return {
            "decision": "DENY",
            "reason": "SELF_REPORT_CANNOT_VERIFY",
            "verified": False,
        }

    return {
        "decision": "ALLOW",
        "member_id": signal.get("member_id"),
        "skill_id": signal.get("skill_id"),
        "status": status,
        "verification_method": method,
        "evidence_ref": evidence_ref,
        "verified": status == "VERIFIED",
        "production_authority": False,
        "statutory_licence": False,
    }


def to_world_event(signal: Mapping[str, Any], correlation_id: str) -> Dict[str, Any]:
    normalized = normalize_skill_signal(signal)
    if normalized["decision"] != "ALLOW" or not normalized.get("verified"):
        return {
            "decision": "HOLD",
            "reason": normalized.get("reason", "SKILL_SIGNAL_NOT_VERIFIED"),
            "production_authority": False,
        }

    return {
        "decision": "ALLOW",
        "event_type": "skill.signal_verified",
        "member_id": normalized["member_id"],
        "skill_id": normalized["skill_id"],
        "verification_method": normalized["verification_method"],
        "evidence_ref": normalized["evidence_ref"],
        "correlation_id": correlation_id,
        "production_authority": False,
    }
