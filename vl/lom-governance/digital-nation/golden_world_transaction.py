"""LOM Digital Nation P0 Golden World Transaction validator.

Non-production reference implementation.
It validates ordering, evidence presence, and bounded authority only.
It never calls payment providers, performs payouts, or mutates Production.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence


REQUIRED_SEQUENCE: Sequence[str] = (
    "member.registered",
    "member.identity_verified",
    "skill.signal_verified",
    "opportunity.matched",
    "offer.accepted",
    "order.created",
    "payment.confirmed",
    "delivery.submitted",
    "delivery.accepted",
    "earning.recorded",
    "reputation.updated",
    "referral.attributed",
)

EVIDENCE_REQUIRED = {
    "member.registered",
    "member.identity_verified",
    "skill.signal_verified",
    "business.registered",
    "payment.confirmed",
    "delivery.submitted",
    "delivery.accepted",
    "reputation.updated",
    "referral.attributed",
    "dispute.opened",
    "dispute.resolved",
}

CONSEQUENTIAL_EVENTS = {
    "payment.confirmed",
    "earning.recorded",
    "dispute.resolved",
}

PROHIBITED_AUTHORITY_CLAIMS = {
    "sovereign_state",
    "government_authority",
    "legal_citizenship",
    "banking_licence",
    "legal_tender_issuer",
    "statutory_land_title",
    "court_judgment",
}


@dataclass(frozen=True)
class ValidationResult:
    decision: str
    reasons: List[str]
    correlation_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.decision == "ALLOW"


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def validate_event(event: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    for field in ("event_id", "event_type", "occurred_at", "actor_id", "source_system", "correlation_id"):
        if not _nonempty(event.get(field)):
            errors.append(f"MISSING_{field.upper()}")

    event_type = str(event.get("event_type", ""))

    if event_type in EVIDENCE_REQUIRED and not _nonempty(event.get("evidence_ref")):
        errors.append("MISSING_EVIDENCE")

    authority = event.get("authority_context") or {}
    claims = set(authority.get("claims") or [])
    bad_claims = claims.intersection(PROHIBITED_AUTHORITY_CLAIMS)
    if bad_claims:
        errors.append("PROHIBITED_AUTHORITY_CLAIM:" + ",".join(sorted(bad_claims)))

    if event_type in CONSEQUENTIAL_EVENTS:
        if authority.get("decision") not in {"ALLOW", "HUMAN_APPROVED"}:
            errors.append("CONSEQUENTIAL_AUTHORITY_NOT_APPROVED")

    if event_type == "payment.confirmed":
        if not _nonempty(event.get("payment_reference_id")):
            errors.append("MISSING_PAYMENT_REFERENCE")
        if event.get("evidence_source") in {None, "", "user_assertion", "synthetic_claim"}:
            errors.append("INVALID_PAYMENT_EVIDENCE_SOURCE")

    if event_type == "earning.recorded":
        for field in ("gross_amount", "fees", "net_amount", "currency", "beneficiary_id"):
            if not _nonempty(event.get(field)):
                errors.append(f"MISSING_{field.upper()}")

    return errors


def validate_golden_world_transaction(events: Iterable[Mapping[str, Any]]) -> ValidationResult:
    items = list(events)
    if not items:
        return ValidationResult("DENY", ["EMPTY_TRANSACTION"])

    correlation_ids = {str(e.get("correlation_id")) for e in items if _nonempty(e.get("correlation_id"))}
    if len(correlation_ids) != 1:
        return ValidationResult("DENY", ["CORRELATION_ID_MISMATCH"])

    correlation_id = next(iter(correlation_ids))
    reasons: List[str] = []

    seen_types = [str(e.get("event_type", "")) for e in items]

    cursor = 0
    for expected in REQUIRED_SEQUENCE:
        try:
            index = seen_types.index(expected, cursor)
        except ValueError:
            reasons.append(f"MISSING_OR_OUT_OF_ORDER:{expected}")
            continue
        cursor = index + 1

    ids = [e.get("event_id") for e in items if _nonempty(e.get("event_id"))]
    if len(ids) != len(set(ids)):
        reasons.append("DUPLICATE_EVENT_ID")

    for idx, event in enumerate(items):
        for error in validate_event(event):
            reasons.append(f"EVENT_{idx}:{error}")

    payment_index = next((i for i, e in enumerate(items) if e.get("event_type") == "payment.confirmed"), None)
    earning_index = next((i for i, e in enumerate(items) if e.get("event_type") == "earning.recorded"), None)
    acceptance_index = next((i for i, e in enumerate(items) if e.get("event_type") == "delivery.accepted"), None)

    if earning_index is not None:
        if payment_index is None or payment_index > earning_index:
            reasons.append("EARNING_BEFORE_PAYMENT")
        if acceptance_index is None or acceptance_index > earning_index:
            reasons.append("EARNING_BEFORE_ACCEPTANCE")

    if reasons:
        return ValidationResult("DENY", reasons, correlation_id)

    return ValidationResult("ALLOW", [], correlation_id)


def preview_summary(events: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    result = validate_golden_world_transaction(events)
    return {
        "schema": "lom.digital-nation.golden-world-validation/1",
        "mode": "PREVIEW_SYNTHETIC_ONLY",
        "decision": result.decision,
        "correlation_id": result.correlation_id,
        "reasons": result.reasons,
        "production_authority": False,
        "payment_execution": False,
        "payout_execution": False,
    }
