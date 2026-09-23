from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

LIFECYCLE = [
    "LEAD","DISCOVERY","QUALIFICATION","QUOTATION","APPROVAL","PAYMENT",
    "PRODUCTION","QA_UAT","DELIVERY","ACCEPTANCE","INVOICE_EINVOICE",
    "ACCOUNTING","SUPPORT","REPEAT_REFERRAL",
]

ALLOWED_NEXT = {state: (LIFECYCLE[i + 1] if i + 1 < len(LIFECYCLE) else None)
                for i, state in enumerate(LIFECYCLE)}

HARD_AUTHORITY_STATES = {
    "PRODUCTION": "production_authority",
}

def _digest(value: Any) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

def compose_job_view(*, job_id: str, org_id: str, customer_ref: str,
                     current_state: str, evidence: dict[str, Any],
                     blockers: list[str] | None = None,
                     action_mode: str = "AUTO") -> dict[str, Any]:
    if current_state not in LIFECYCLE:
        return {"decision": "HOLD", "reason": "UNKNOWN_LIFECYCLE_STATE"}
    if not job_id or not org_id or not customer_ref:
        return {"decision": "HOLD", "reason": "IDENTITY_REQUIRED"}

    blockers = list(blockers or [])
    next_state = ALLOWED_NEXT[current_state]
    next_action = "CLOSED_LOOP_COMPLETE" if next_state is None else f"EVALUATE_{next_state}"

    view = {
        "schema": "lds.job-command-view/1",
        "decision": "PASS",
        "job_id": job_id,
        "org_id": org_id,
        "customer_ref": customer_ref,
        "current_state": current_state,
        "next_action": next_action,
        "action_mode": action_mode,
        "blocker_reason": blockers[0] if blockers else None,
        "blockers": blockers,
        "commercial_status": evidence.get("commercial_status"),
        "payment_status": evidence.get("payment_status"),
        "production_status": evidence.get("production_status"),
        "qa_uat_status": evidence.get("qa_uat_status"),
        "delivery_status": evidence.get("delivery_status"),
        "invoice_status": evidence.get("invoice_status"),
        "accounting_status": evidence.get("accounting_status"),
        "support_status": evidence.get("support_status"),
        "evidence_freshness": evidence.get("evidence_freshness", "UNKNOWN"),
        "unit_economics": evidence.get("unit_economics"),
        "retry_recovery": evidence.get("retry_recovery"),
    }
    view["view_digest"] = _digest(view)
    return view

def evaluate_event(*, current_state: str, proposed_state: str,
                   event_id: str, signed: bool, idempotency_key: str,
                   consumed_keys: set[str] | None,
                   evidence_refs: list[str] | None,
                   authorities: dict[str, bool] | None = None) -> dict[str, Any]:
    consumed_keys = consumed_keys or set()
    authorities = authorities or {}

    if current_state not in LIFECYCLE or proposed_state not in LIFECYCLE:
        return {"decision": "HOLD", "reason": "UNKNOWN_LIFECYCLE_STATE"}
    if ALLOWED_NEXT[current_state] != proposed_state:
        return {"decision": "HOLD", "reason": "ILLEGAL_TRANSITION"}
    if not event_id or not idempotency_key:
        return {"decision": "HOLD", "reason": "EVENT_AND_IDEMPOTENCY_REQUIRED"}
    if idempotency_key in consumed_keys:
        return {"decision": "IDEMPOTENT_REPLAY", "reason": "ALREADY_CONSUMED"}
    if signed is not True:
        return {"decision": "HOLD", "reason": "UNVERIFIED_EVENT"}
    if not evidence_refs:
        return {"decision": "HOLD", "reason": "EVIDENCE_REQUIRED"}

    authority_key = HARD_AUTHORITY_STATES.get(proposed_state)
    if authority_key and authorities.get(authority_key) is not True:
        return {"decision": "HOLD", "reason": "HUMAN_AUTHORITY_REQUIRED"}

    receipt_body = {
        "event_id": event_id,
        "from_state": current_state,
        "to_state": proposed_state,
        "idempotency_key": idempotency_key,
        "evidence_refs": sorted(evidence_refs),
    }
    return {
        "decision": "PASS",
        "schema": "lds.job-transition-receipt/1",
        **receipt_body,
        "receipt_digest": _digest(receipt_body),
        "production_activation_authorized": False,
    }
