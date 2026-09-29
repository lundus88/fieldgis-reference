from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from hashlib import sha256
import json

STATES = {
    "DRAFT","FUNDED","READY","ASSIGNED","IN_PROGRESS","SUBMITTED","QA_CHECK",
    "REVISION_REQUIRED","ESCALATED","REJECTED","PASS","PAYABLE",
    "PAYOUT_PROCESSING","PAID","RECONCILED","CLOSED","CANCELLED",
    "PAYMENT_HELD","DISPUTED","SECURITY_REVIEW"
}

HARD_FAIL_CODES = {
    "MATERIAL_FACT_CHANGED",
    "PRICE_OR_OFFER_INVENTED",
    "FAKE_TESTIMONIAL",
    "FABRICATED_RESULT",
    "SERIOUS_POLICY_VIOLATION",
}

ALLOWED_TRANSITIONS = {
    ("DRAFT","FUND_CONFIRMED"): "FUNDED",
    ("FUNDED","MARK_READY"): "READY",
    ("READY","ASSIGN_WORKER"): "ASSIGNED",
    ("ASSIGNED","START_TASK"): "IN_PROGRESS",
    ("IN_PROGRESS","SUBMIT_WORK"): "SUBMITTED",
    ("SUBMITTED","START_QA"): "QA_CHECK",
    ("QA_CHECK","QA_PASS"): "PASS",
    ("QA_CHECK","QA_REVISION"): "REVISION_REQUIRED",
    ("QA_CHECK","QA_ESCALATE"): "ESCALATED",
    ("QA_CHECK","QA_REJECT"): "REJECTED",
    ("REVISION_REQUIRED","START_REVISION"): "IN_PROGRESS",
    ("ESCALATED","ESCALATION_APPROVE"): "PASS",
    ("ESCALATED","ESCALATION_REVISION"): "REVISION_REQUIRED",
    ("ESCALATED","ESCALATION_REJECT"): "REJECTED",
    ("PASS","CREATE_PAYABLE"): "PAYABLE",
    ("PAYABLE","PROCESS_PAYOUT"): "PAYOUT_PROCESSING",
    ("PAYOUT_PROCESSING","CONFIRM_PAID"): "PAID",
    ("PAID","RECONCILE"): "RECONCILED",
    ("RECONCILED","CLOSE_TASK"): "CLOSED",
}

ACTOR_EVENTS = {
    "SYSTEM": {"MARK_READY","ASSIGN_WORKER","CLOSE_TASK","SECURITY_FLAG"},
    "FINANCE": {"FUND_CONFIRMED","CREATE_PAYABLE","PROCESS_PAYOUT","RECONCILE","HOLD_PAYMENT"},
    "WORKER": {"START_TASK","SUBMIT_WORK","START_REVISION"},
    "QA_SERVICE": {"START_QA","QA_PASS","QA_REVISION","QA_ESCALATE","QA_REJECT"},
    "REVIEWER": {"ESCALATION_APPROVE","ESCALATION_REVISION","ESCALATION_REJECT","OPEN_DISPUTE"},
    "PAYMENT_ADAPTER": {"CONFIRM_PAID"},
}

@dataclass
class FundingAllocation:
    funding_id: str
    approved_minor: int
    reserved_minor: int
    spent_minor: int = 0
    currency: str = "MYR"

    def valid_for(self, amount_minor: int) -> bool:
        return (
            amount_minor > 0
            and self.approved_minor >= self.reserved_minor >= amount_minor
            and self.spent_minor + amount_minor <= self.approved_minor
        )

@dataclass
class WorkerProfile:
    worker_id: str
    stage: str = "STARTER"
    active: bool = True
    integrity_clear: bool = True

@dataclass
class Task:
    task_id: str
    funding_id: Optional[str] = None
    worker_id: Optional[str] = None
    status: str = "DRAFT"
    worker_fee_minor: int = 0
    revision_count: int = 0
    qa_result_id: Optional[str] = None
    security_hold: bool = False
    dispute_open: bool = False
    audit: List[Dict] = field(default_factory=list)

@dataclass(frozen=True)
class QAResult:
    qa_result_id: str
    factual_consistency: int
    hook_quality: int
    clarity_readability: int
    message_focus: int
    cta_quality: int
    duration_format: int
    tone_audience_fit: int
    policy_safety: int
    confidence: float
    reason_codes: Tuple[str, ...] = ()

    @property
    def score(self) -> int:
        return sum([
            self.factual_consistency,
            self.hook_quality,
            self.clarity_readability,
            self.message_focus,
            self.cta_quality,
            self.duration_format,
            self.tone_audience_fit,
            self.policy_safety,
        ])

@dataclass(frozen=True)
class EarningsEntry:
    ledger_entry_id: str
    task_id: str
    worker_id: str
    amount_minor: int
    currency: str
    status: str
    funding_id: str

def digest(value: Dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",",":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()

def qa_decision(q: QAResult) -> Dict:
    if any(code in HARD_FAIL_CODES for code in q.reason_codes):
        return {"decision":"REJECT","score":q.score,"confidence":q.confidence,"reason":"HARD_FAIL"}
    if q.confidence < 0.80:
        return {"decision":"ESCALATE","score":q.score,"confidence":q.confidence,"reason":"LOW_CONFIDENCE"}
    if q.score >= 85:
        return {"decision":"PASS","score":q.score,"confidence":q.confidence,"reason":"THRESHOLD_MET"}
    if q.score >= 70:
        return {"decision":"REVISION","score":q.score,"confidence":q.confidence,"reason":"IMPROVEMENT_REQUIRED"}
    if q.score < 50:
        return {"decision":"REJECT","score":q.score,"confidence":q.confidence,"reason":"QUALITY_FLOOR_FAILED"}
    return {"decision":"ESCALATE","score":q.score,"confidence":q.confidence,"reason":"BORDERLINE_REVIEW"}

def _audit(task: Task, event: str, actor: str, result: str, reason: str, previous: str, nxt: str) -> None:
    row = {
        "task_id": task.task_id,
        "event": event,
        "actor": actor,
        "result": result,
        "reason": reason,
        "previous_status": previous,
        "next_status": nxt,
        "revision_count": task.revision_count,
    }
    task.audit.append({**row, "digest": digest(row)})

def transition_task(
    task: Task,
    event: str,
    actor: str,
    *,
    funding: Optional[FundingAllocation] = None,
    worker: Optional[WorkerProfile] = None,
    qa: Optional[QAResult] = None,
    provider_success: bool = False,
    reconciliation_ok: bool = False,
) -> Dict:
    previous = task.status

    if actor not in ACTOR_EVENTS or event not in ACTOR_EVENTS[actor]:
        _audit(task,event,actor,"DENY","UNAUTHORIZED_ACTOR_EVENT",previous,previous)
        return {"decision":"DENY","reason":"UNAUTHORIZED_ACTOR_EVENT","status":task.status}

    if event == "SECURITY_FLAG":
        task.status = "SECURITY_REVIEW"
        task.security_hold = True
        _audit(task,event,actor,"ALLOW","SECURITY_REVIEW_REQUIRED",previous,task.status)
        return {"decision":"ALLOW","status":task.status}

    if event == "OPEN_DISPUTE":
        if task.status not in {"PAYABLE","PAYOUT_PROCESSING","PAID","RECONCILED"}:
            _audit(task,event,actor,"DENY","DISPUTE_STATE_INVALID",previous,previous)
            return {"decision":"DENY","reason":"DISPUTE_STATE_INVALID","status":task.status}
        task.status = "DISPUTED"
        task.dispute_open = True
        _audit(task,event,actor,"ALLOW","DISPUTE_OPENED",previous,task.status)
        return {"decision":"ALLOW","status":task.status}

    if event == "HOLD_PAYMENT":
        if task.status not in {"PAYABLE","PAYOUT_PROCESSING"}:
            _audit(task,event,actor,"DENY","PAYMENT_HOLD_STATE_INVALID",previous,previous)
            return {"decision":"DENY","reason":"PAYMENT_HOLD_STATE_INVALID","status":task.status}
        task.status = "PAYMENT_HELD"
        _audit(task,event,actor,"ALLOW","PAYMENT_HELD_FOR_REVIEW",previous,task.status)
        return {"decision":"ALLOW","status":task.status}

    nxt = ALLOWED_TRANSITIONS.get((task.status,event))
    if nxt is None:
        _audit(task,event,actor,"DENY","TRANSITION_NOT_ALLOWED",previous,previous)
        return {"decision":"DENY","reason":"TRANSITION_NOT_ALLOWED","status":task.status}

    if event == "FUND_CONFIRMED":
        if funding is None or task.funding_id != funding.funding_id or not funding.valid_for(task.worker_fee_minor):
            _audit(task,event,actor,"DENY","FUNDING_INVALID_OR_UNRESERVED",previous,previous)
            return {"decision":"DENY","reason":"FUNDING_INVALID_OR_UNRESERVED","status":task.status}

    if event == "MARK_READY":
        if funding is None or not funding.valid_for(task.worker_fee_minor):
            _audit(task,event,actor,"DENY","READY_REQUIRES_VALID_FUNDING",previous,previous)
            return {"decision":"DENY","reason":"READY_REQUIRES_VALID_FUNDING","status":task.status}

    if event == "ASSIGN_WORKER":
        if worker is None or not worker.active or not worker.integrity_clear:
            _audit(task,event,actor,"DENY","WORKER_NOT_ELIGIBLE",previous,previous)
            return {"decision":"DENY","reason":"WORKER_NOT_ELIGIBLE","status":task.status}
        task.worker_id = worker.worker_id

    if event in {"START_TASK","SUBMIT_WORK","START_REVISION"}:
        if worker is None or worker.worker_id != task.worker_id or not worker.active:
            _audit(task,event,actor,"DENY","WORKER_OWNERSHIP_REQUIRED",previous,previous)
            return {"decision":"DENY","reason":"WORKER_OWNERSHIP_REQUIRED","status":task.status}

    if event == "START_REVISION" and task.revision_count == 0:
        _audit(task,event,actor,"DENY","REVISION_NOT_REQUESTED",previous,previous)
        return {"decision":"DENY","reason":"REVISION_NOT_REQUESTED","status":task.status}

    if event in {"QA_PASS","QA_REVISION","QA_ESCALATE","QA_REJECT"}:
        if qa is None:
            _audit(task,event,actor,"DENY","QA_EVIDENCE_REQUIRED",previous,previous)
            return {"decision":"DENY","reason":"QA_EVIDENCE_REQUIRED","status":task.status}
        decision = qa_decision(qa)["decision"]
        expected = {
            "QA_PASS":"PASS",
            "QA_REVISION":"REVISION",
            "QA_ESCALATE":"ESCALATE",
            "QA_REJECT":"REJECT",
        }[event]
        if decision != expected:
            _audit(task,event,actor,"DENY","QA_DECISION_MISMATCH",previous,previous)
            return {"decision":"DENY","reason":"QA_DECISION_MISMATCH","status":task.status}
        task.qa_result_id = qa.qa_result_id
        if event == "QA_REVISION":
            if task.revision_count >= 2:
                _audit(task,event,actor,"DENY","REVISION_LIMIT_REACHED",previous,previous)
                return {"decision":"DENY","reason":"REVISION_LIMIT_REACHED","status":task.status}
            task.revision_count += 1

    if event == "ESCALATION_REVISION":
        if task.revision_count >= 2:
            _audit(task,event,actor,"DENY","REVISION_LIMIT_REACHED",previous,previous)
            return {"decision":"DENY","reason":"REVISION_LIMIT_REACHED","status":task.status}
        task.revision_count += 1

    if event in {"QA_PASS","ESCALATION_APPROVE"} and not (task.qa_result_id or qa):
        _audit(task,event,actor,"DENY","PASS_REQUIRES_QA_EVIDENCE",previous,previous)
        return {"decision":"DENY","reason":"PASS_REQUIRES_QA_EVIDENCE","status":task.status}

    if event == "CREATE_PAYABLE":
        if task.security_hold or task.dispute_open:
            _audit(task,event,actor,"DENY","PAYMENT_RISK_HOLD",previous,previous)
            return {"decision":"DENY","reason":"PAYMENT_RISK_HOLD","status":task.status}
        if funding is None or not funding.valid_for(task.worker_fee_minor):
            _audit(task,event,actor,"DENY","PAYABLE_REQUIRES_RESERVED_FUNDING",previous,previous)
            return {"decision":"DENY","reason":"PAYABLE_REQUIRES_RESERVED_FUNDING","status":task.status}
        if not task.qa_result_id:
            _audit(task,event,actor,"DENY","PAYABLE_REQUIRES_QA_PASS_EVIDENCE",previous,previous)
            return {"decision":"DENY","reason":"PAYABLE_REQUIRES_QA_PASS_EVIDENCE","status":task.status}

    if event == "CONFIRM_PAID" and not provider_success:
        _audit(task,event,actor,"DENY","PROVIDER_PAYMENT_NOT_VERIFIED",previous,previous)
        return {"decision":"DENY","reason":"PROVIDER_PAYMENT_NOT_VERIFIED","status":task.status}

    if event == "RECONCILE" and not reconciliation_ok:
        _audit(task,event,actor,"DENY","RECONCILIATION_FAILED",previous,previous)
        return {"decision":"DENY","reason":"RECONCILIATION_FAILED","status":task.status}

    task.status = nxt
    _audit(task,event,actor,"ALLOW","GUARDS_PASSED",previous,nxt)
    return {"decision":"ALLOW","status":task.status}

def create_payable_entitlement(task: Task, funding: FundingAllocation) -> EarningsEntry:
    if task.status != "PAYABLE":
        raise ValueError("TASK_NOT_PAYABLE")
    if not task.worker_id:
        raise ValueError("WORKER_REQUIRED")
    if not task.qa_result_id:
        raise ValueError("QA_EVIDENCE_REQUIRED")
    if not funding.valid_for(task.worker_fee_minor):
        raise ValueError("FUNDING_INVALID")
    key = digest({"task_id":task.task_id,"worker_id":task.worker_id,"funding_id":funding.funding_id})
    return EarningsEntry(
        ledger_entry_id=key,
        task_id=task.task_id,
        worker_id=task.worker_id,
        amount_minor=task.worker_fee_minor,
        currency=funding.currency,
        status="ELIGIBLE_FOR_HUMAN_PAYOUT_REVIEW",
        funding_id=funding.funding_id,
    )

def worker_reputation_evidence(
    *,
    worker_id: str,
    task_id: str,
    accepted: bool,
    revision_count: int,
    integrity_event: bool,
    on_time: bool,
    source_event_id: str,
    evidence_ref: str,
) -> List[Dict]:
    """Emit bounded evidence for the authoritative LOM Trust reputation owner.

    This capability does not calculate or own an aggregate reputation score.
    """
    if not source_event_id or not evidence_ref:
        raise ValueError("REPUTATION_EVIDENCE_REQUIRED")

    events = [
        {
            "member_id": worker_id,
            "task_id": task_id,
            "dimension": "DELIVERY_RELIABILITY",
            "reason_code": "DELIVERY_ACCEPTED" if accepted else "DELIVERY_NOT_ACCEPTED",
            "signal": "POSITIVE" if accepted else "ADVERSE",
            "evidence_ref": evidence_ref,
            "source_event_id": source_event_id,
            "consumer": "LOM Trust",
            "authoritative_aggregate": False,
        },
        {
            "member_id": worker_id,
            "task_id": task_id,
            "dimension": "DELIVERY_RELIABILITY",
            "reason_code": "ON_TIME" if on_time else "LATE",
            "signal": "POSITIVE" if on_time else "ADVERSE",
            "evidence_ref": evidence_ref,
            "source_event_id": source_event_id,
            "consumer": "LOM Trust",
            "authoritative_aggregate": False,
        },
        {
            "member_id": worker_id,
            "task_id": task_id,
            "dimension": "DELIVERY_RELIABILITY",
            "reason_code": "REVISION_COUNT",
            "signal": "OBSERVATION",
            "value": min(max(revision_count, 0), 2),
            "evidence_ref": evidence_ref,
            "source_event_id": source_event_id,
            "consumer": "LOM Trust",
            "authoritative_aggregate": False,
        },
    ]
    if integrity_event:
        events.append({
            "member_id": worker_id,
            "task_id": task_id,
            "dimension": "POLICY_COMPLIANCE",
            "reason_code": "INTEGRITY_REVIEW_REQUIRED",
            "signal": "REVIEW_REQUIRED",
            "evidence_ref": evidence_ref,
            "source_event_id": source_event_id,
            "consumer": "LOM Trust",
            "authoritative_aggregate": False,
        })
    return events

def evaluate_scale_gate(metrics: Dict) -> Dict:
    required = {
        "first_pass_rate",
        "final_pass_rate",
        "serious_fact_errors",
        "revision_rate",
        "median_minutes",
        "human_intervention_rate",
        "duplicate_entitlements",
        "unfunded_entitlements",
        "unauthorized_transitions",
        "synthetic_only",
    }
    missing = sorted(required - set(metrics))
    if missing:
        return {"decision":"HOLD","reason":"METRICS_MISSING","missing":missing}

    hard_stop = (
        metrics["serious_fact_errors"] > 0
        or metrics["duplicate_entitlements"] > 0
        or metrics["unfunded_entitlements"] > 0
        or metrics["unauthorized_transitions"] > 0
        or metrics["synthetic_only"] is not True
    )
    if hard_stop:
        return {"decision":"NO_GO","reason":"HARD_STOP"}

    go = (
        metrics["first_pass_rate"] >= 0.80
        and metrics["final_pass_rate"] >= 0.95
        and metrics["revision_rate"] <= 0.20
        and metrics["median_minutes"] <= 10
        and metrics["human_intervention_rate"] <= 0.20
    )
    return {
        "decision":"READY_FOR_HUMAN_GO_NO_GO" if go else "HOLD",
        "reason":"THRESHOLDS_MET" if go else "THRESHOLDS_NOT_MET",
        "production_authority":"HUMAN_ONLY",
        "live_pilot_authority":"HUMAN_ONLY",
    }
