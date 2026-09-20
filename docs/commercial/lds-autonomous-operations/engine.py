#!/usr/bin/env python3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
import json

ROOT=Path(__file__).resolve().parent
REGISTRY=json.loads((ROOT/"capability_registry.json").read_text())
CAPABILITIES={x["id"]:x for x in REGISTRY["capabilities"]}

@dataclass(frozen=True)
class AutoKickoffEvidence:
    payment_reconciled: bool
    confirmed_requirement_scope: bool
    capability_id: str
    capacity_available: bool
    unit_economics_status: str
    unresolved_material_risk: bool=False
    unverified_material_integration: bool=False
    fraud_or_abuse_hold: bool=False
    compliance_review_required: bool=False

@dataclass(frozen=True)
class CapacitySnapshot:
    active_jobs: int
    max_concurrent_jobs: int
    estimated_new_job_weight: int=1
    reserved_capacity: int=0

@dataclass(frozen=True)
class OutcomeSnapshot:
    required_criteria: List[str]
    passed_criteria: List[str]
    customer_acceptance_required: bool=True
    customer_accepted: bool=False

@dataclass(frozen=True)
class RecoverySnapshot:
    failure_class: str
    retry_count: int
    max_retries: int
    estimated_retry_cost: float
    remaining_cost_budget: float
    rollback_evidence_present: bool
    production_impact: bool=False
    irreversible_customer_impact: bool=False

@dataclass(frozen=True)
class ProjectState:
    state: str
    terminal: bool=False
    next_trigger: str=""
    blocker_reason: str=""
    evidence_fresh: bool=True
    action_mode: str="AUTO"
    notes: List[str]=field(default_factory=list)

def capability_decision(capability_id:str)->Dict:
    c=CAPABILITIES.get(capability_id)
    if not c:
        return {"status":"HUMAN_GATE","reason":"UNKNOWN_CAPABILITY","supported":False}
    if c["status"]=="DISCOVERY_ONLY":
        return {"status":"HUMAN_GATE","reason":"DISCOVERY_ONLY_CAPABILITY","supported":False,"capability":c}
    return {
        "status":c["default_action_mode"],
        "reason":"CAPABILITY_POLICY_MATCH",
        "supported":c["status"] in {"SUPPORTED","SUPPORTED_WITH_GUARDRAILS"},
        "capability":c
    }

def capacity_decision(s:CapacitySnapshot)->Dict:
    if min(s.active_jobs,s.max_concurrent_jobs,s.estimated_new_job_weight,s.reserved_capacity) < 0:
        return {"status":"HUMAN_GATE","reason":"INVALID_CAPACITY_EVIDENCE"}
    usable=max(0,s.max_concurrent_jobs-s.reserved_capacity)
    if s.active_jobs+s.estimated_new_job_weight <= usable:
        return {"status":"AUTO","reason":"CAPACITY_AVAILABLE","queue_required":False}
    return {"status":"AUTO_NOTIFY","reason":"QUEUED_CAPACITY","queue_required":True}

def auto_kickoff(e:AutoKickoffEvidence)->Dict:
    cap=capability_decision(e.capability_id)
    if not e.payment_reconciled:
        return {"status":"HUMAN_GATE","reason":"PAYMENT_RECONCILIATION_REQUIRED","eligible":False}
    if not e.confirmed_requirement_scope:
        return {"status":"HUMAN_GATE","reason":"CONFIRMED_REQUIREMENT_SCOPE_REQUIRED","eligible":False}
    if not cap["supported"]:
        return {"status":"HUMAN_GATE","reason":cap["reason"],"eligible":False}
    if not e.capacity_available:
        return {"status":"AUTO_NOTIFY","reason":"QUEUED_CAPACITY","eligible":False}
    if e.unit_economics_status!="PASS":
        return {"status":"HUMAN_GATE","reason":"UNIT_ECONOMICS_REVIEW_REQUIRED","eligible":False}
    if e.fraud_or_abuse_hold:
        return {"status":"HUMAN_GATE","reason":"FRAUD_OR_ABUSE_HOLD","eligible":False}
    if e.compliance_review_required or e.unresolved_material_risk:
        return {"status":"HUMAN_GATE","reason":"MATERIAL_RISK_REVIEW_REQUIRED","eligible":False}
    if e.unverified_material_integration:
        return {"status":"HUMAN_GATE","reason":"MATERIAL_INTEGRATION_NOT_VERIFIED","eligible":False}
    return {
        "status":cap["status"],
        "reason":"AUTONOMOUS_KICKOFF_ELIGIBLE",
        "eligible":True,
        "receipt":"autonomous_kickoff_eligibility",
        "production_authority":False
    }

def outcome_decision(s:OutcomeSnapshot)->Dict:
    required=set(s.required_criteria)
    passed=set(s.passed_criteria)
    missing=sorted(required-passed)
    if not required:
        return {"status":"HUMAN_GATE","reason":"ACCEPTANCE_CRITERIA_REQUIRED","outcome_pass":False}
    if missing:
        return {"status":"AUTO","reason":"OUTCOME_REMEDIATION_REQUIRED","outcome_pass":False,"missing":missing}
    if s.customer_acceptance_required and not s.customer_accepted:
        return {"status":"AUTO_NOTIFY","reason":"WAITING_CUSTOMER_ACCEPTANCE","outcome_pass":False}
    return {"status":"AUTO","reason":"OUTCOME_ACCEPTANCE_PASS","outcome_pass":True}

def recovery_decision(s:RecoverySnapshot)->Dict:
    if s.production_impact or s.irreversible_customer_impact:
        return {"status":"HUMAN_GATE","reason":"CONSEQUENTIAL_RECOVERY_REQUIRES_HUMAN"}
    if not s.rollback_evidence_present:
        return {"status":"HUMAN_GATE","reason":"ROLLBACK_EVIDENCE_REQUIRED"}
    if s.retry_count >= s.max_retries:
        return {"status":"HUMAN_GATE","reason":"RETRY_BUDGET_EXHAUSTED"}
    if s.estimated_retry_cost > s.remaining_cost_budget:
        return {"status":"HUMAN_GATE","reason":"RECOVERY_COST_BUDGET_EXCEEDED"}
    return {"status":"AUTO_NOTIFY","reason":"BOUNDED_SELF_REPAIR_ALLOWED","next":"DIAGNOSE_REPAIR_RETEST"}

def no_idle_check(p:ProjectState)->Dict:
    if p.terminal:
        return {"status":"PASS","reason":"TERMINAL_STATE"}
    if not p.evidence_fresh:
        return {"status":"HUMAN_GATE","reason":"STALE_PROJECT_EVIDENCE"}
    if p.next_trigger:
        return {"status":"PASS","reason":"NEXT_TRIGGER_PRESENT","next_trigger":p.next_trigger}
    if p.blocker_reason:
        return {"status":"PASS","reason":"DOCUMENTED_BLOCKER","blocker_reason":p.blocker_reason}
    return {"status":"HUMAN_GATE","reason":"IDLE_WITHOUT_DOCUMENTED_REASON"}
