"""Evidence-backed reputation adapter for LOM Digital Nation."""

from __future__ import annotations
from collections import Counter
from typing import Any, Dict, Iterable, Mapping

ALLOWED_DIMENSIONS = {
    "DELIVERY_RELIABILITY",
    "TRANSACTION_INTEGRITY",
    "VERIFIED_SKILL",
    "DISPUTE_OUTCOME",
    "POLICY_COMPLIANCE",
}

def validate_reputation_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    required = ("member_id", "dimension", "reason_code", "evidence_ref", "source_event_id")
    missing = [f for f in required if not event.get(f)]
    if missing:
        return {"decision": "DENY", "reason": "MISSING:" + ",".join(missing)}

    dimension = str(event["dimension"]).upper()
    if dimension not in ALLOWED_DIMENSIONS:
        return {"decision": "DENY", "reason": "UNSUPPORTED_DIMENSION"}

    if event.get("global_score") is not None:
        return {"decision": "DENY", "reason": "OPAQUE_GLOBAL_SCORE_FORBIDDEN"}

    if event.get("sanction") is not None:
        return {"decision": "DENY", "reason": "SANCTION_OUTSIDE_REPUTATION_ADAPTER"}

    return {
        "decision": "ALLOW",
        "member_id": event["member_id"],
        "dimension": dimension,
        "reason_code": event["reason_code"],
        "evidence_ref": event["evidence_ref"],
        "source_event_id": event["source_event_id"],
        "production_authority": False,
    }

def summarize(events: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    accepted = []
    rejected = []
    for event in events:
        decision = validate_reputation_event(event)
        if decision["decision"] == "ALLOW":
            accepted.append(decision)
        else:
            rejected.append(decision)

    counts = Counter(e["dimension"] for e in accepted)
    return {
        "schema": "lom.digital-nation.reputation-summary/1",
        "accepted_events": len(accepted),
        "rejected_events": len(rejected),
        "dimension_counts": dict(sorted(counts.items())),
        "single_global_score": None,
        "production_authority": False,
    }
