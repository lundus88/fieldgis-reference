#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List

WAIT_STATES={
    "WAITING_CUSTOMER",
    "WAITING_PAYMENT",
    "WAITING_DEPENDENCY",
    "QUEUED_CAPACITY",
    "HUMAN_APPROVAL_REQUIRED",
    "QA_BLOCKED",
    "RECOVERY_IN_PROGRESS",
    "EXTERNAL_PROVIDER_OUTAGE",
    "COMPLIANCE_REVIEW",
    "COMMERCIAL_REVIEW",
}

@dataclass(frozen=True)
class WaitState:
    state: str
    elapsed_minutes: int
    soft_timeout_minutes: int
    hard_timeout_minutes: int
    owner_present: bool
    release_condition_present: bool
    next_check_minutes: int
    human_authority_required: bool=False

def wait_guard(w:WaitState)->Dict:
    if w.state not in WAIT_STATES:
        return {"status":"HUMAN_GATE","reason":"UNKNOWN_WAIT_STATE"}
    if min(w.elapsed_minutes,w.soft_timeout_minutes,w.hard_timeout_minutes,w.next_check_minutes) < 0:
        return {"status":"HUMAN_GATE","reason":"INVALID_WAIT_TIMER"}
    if not w.owner_present or not w.release_condition_present:
        return {"status":"HUMAN_GATE","reason":"UNOWNED_OR_UNRELEASABLE_WAIT"}
    if w.hard_timeout_minutes < w.soft_timeout_minutes:
        return {"status":"HUMAN_GATE","reason":"INVALID_TIMEOUT_POLICY"}
    if w.elapsed_minutes >= w.hard_timeout_minutes:
        return {
            "status":"HUMAN_GATE",
            "reason":"HARD_TIMEOUT_ESCALATION",
            "auto_approval_allowed":False,
            "required_action":"ESCALATE_OWNER_AND_REPLAN"
        }
    if w.elapsed_minutes >= w.soft_timeout_minutes:
        return {
            "status":"AUTO_NOTIFY",
            "reason":"SOFT_TIMEOUT_ESCALATION",
            "auto_approval_allowed":False,
            "required_action":"REMIND_OR_REASSIGN_WITHIN_POLICY"
        }
    return {
        "status":"PASS",
        "reason":"WAIT_WITHIN_POLICY",
        "next_check_minutes":w.next_check_minutes,
        "auto_approval_allowed":False
    }

@dataclass(frozen=True)
class QueueItem:
    project_id: str
    base_priority: int
    waiting_minutes: int
    deadline_risk: bool=False
    customer_impact_risk: bool=False
    human_gate: bool=False

def queue_rank(items:List[QueueItem], aging_interval_minutes:int=60)->Dict:
    if aging_interval_minutes <= 0:
        return {"status":"HUMAN_GATE","reason":"INVALID_AGING_POLICY"}
    ranked=[]
    for i in items:
        if i.base_priority < 0 or i.waiting_minutes < 0:
            return {"status":"HUMAN_GATE","reason":"INVALID_QUEUE_EVIDENCE"}
        aging=i.waiting_minutes//aging_interval_minutes
        risk_bonus=(3 if i.deadline_risk else 0)+(3 if i.customer_impact_risk else 0)
        score=i.base_priority+aging+risk_bonus
        ranked.append({
            "project_id":i.project_id,
            "score":score,
            "human_gate":i.human_gate,
            "waiting_minutes":i.waiting_minutes
        })
    ranked.sort(key=lambda x:(-x["score"],-x["waiting_minutes"],x["project_id"]))
    return {"status":"PASS","reason":"STARVATION_RESISTANT_QUEUE","ranked":ranked}

@dataclass(frozen=True)
class ProviderState:
    provider_id: str
    available: bool
    fallback_provider_id: str=""
    fallback_certified: bool=False
    operation_reversible: bool=True
    production_impact: bool=False

def provider_fallback(p:ProviderState)->Dict:
    if p.available:
        return {"status":"PASS","reason":"PRIMARY_PROVIDER_AVAILABLE","provider":p.provider_id}
    if p.production_impact or not p.operation_reversible:
        return {"status":"HUMAN_GATE","reason":"CONSEQUENTIAL_PROVIDER_FAILURE"}
    if p.fallback_provider_id and p.fallback_certified:
        return {
            "status":"AUTO_NOTIFY",
            "reason":"CERTIFIED_FALLBACK_SELECTED",
            "provider":p.fallback_provider_id,
            "production_authority":False
        }
    return {
        "status":"AUTO_NOTIFY",
        "reason":"PROVIDER_OUTAGE_QUEUED",
        "provider":"",
        "next":"RETRY_WITH_BACKOFF_OR_ESCALATE_AT_TIMEOUT"
    }

@dataclass(frozen=True)
class ProgressHeartbeat:
    project_id: str
    elapsed_since_progress_minutes: int
    heartbeat_limit_minutes: int
    has_next_trigger: bool
    documented_blocker: bool
    same_state_reentry_count: int=0
    max_same_state_reentries: int=3

def progress_guard(p:ProgressHeartbeat)->Dict:
    if p.heartbeat_limit_minutes <= 0 or p.elapsed_since_progress_minutes < 0:
        return {"status":"HUMAN_GATE","reason":"INVALID_PROGRESS_POLICY"}
    if p.same_state_reentry_count >= p.max_same_state_reentries:
        return {
            "status":"HUMAN_GATE",
            "reason":"STATE_LOOP_DETECTED",
            "required_action":"DIAGNOSE_OR_REPLAN"
        }
    if p.has_next_trigger or p.documented_blocker:
        if p.elapsed_since_progress_minutes < p.heartbeat_limit_minutes:
            return {"status":"PASS","reason":"PROJECT_HAS_LIVE_PATH"}
        return {
            "status":"AUTO_NOTIFY",
            "reason":"NO_PROGRESS_HEARTBEAT",
            "required_action":"RECHECK_TRIGGER_OR_BLOCKER_OWNER"
        }
    return {
        "status":"HUMAN_GATE",
        "reason":"PROJECT_STUCK_WITHOUT_PATH",
        "required_action":"ASSIGN_OWNER_TRIGGER_OR_BLOCKER"
    }

@dataclass(frozen=True)
class ApprovalGate:
    gate_id: str
    elapsed_minutes: int
    reminder_after_minutes: int
    escalate_after_minutes: int
    approver_assigned: bool
    backup_approver_available: bool
    policy_allows_reassignment: bool

def approval_guard(a:ApprovalGate)->Dict:
    if not a.approver_assigned:
        return {"status":"HUMAN_GATE","reason":"APPROVER_NOT_ASSIGNED","auto_approval_allowed":False}
    if a.elapsed_minutes >= a.escalate_after_minutes:
        if a.backup_approver_available and a.policy_allows_reassignment:
            return {
                "status":"AUTO_NOTIFY",
                "reason":"APPROVAL_ESCALATED_TO_BACKUP",
                "auto_approval_allowed":False
            }
        return {
            "status":"HUMAN_GATE",
            "reason":"APPROVAL_ESCALATION_REQUIRED",
            "auto_approval_allowed":False
        }
    if a.elapsed_minutes >= a.reminder_after_minutes:
        return {
            "status":"AUTO_NOTIFY",
            "reason":"APPROVAL_REMINDER_DUE",
            "auto_approval_allowed":False
        }
    return {"status":"PASS","reason":"APPROVAL_WITHIN_WINDOW","auto_approval_allowed":False}
