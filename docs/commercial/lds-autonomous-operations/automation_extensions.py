#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class DependencyState:
    missing_items: List[str]
    approved_contact_channel: bool
    consent_or_lawful_basis: bool
    reminder_count: int=0
    max_reminders: int=3

def customer_dependency_action(d:DependencyState)->Dict:
    if not d.missing_items:
        return {"status":"PASS","reason":"CUSTOMER_DEPENDENCIES_READY"}
    if not d.approved_contact_channel or not d.consent_or_lawful_basis:
        return {"status":"HUMAN_GATE","reason":"CUSTOMER_CONTACT_NOT_AUTHORISED"}
    if d.reminder_count >= d.max_reminders:
        return {"status":"HUMAN_GATE","reason":"CUSTOMER_DEPENDENCY_ESCALATION_REQUIRED"}
    return {
        "status":"AUTO_NOTIFY",
        "reason":"CLIENT_ACTION_REQUIRED",
        "request_items":sorted(set(d.missing_items)),
        "delivery_clock":"PAUSE_OR_REBASE_PER_POLICY"
    }

@dataclass(frozen=True)
class DeadlineState:
    remaining_hours: float
    estimated_hours_to_finish: float
    queue_delay_hours: float
    contractual_commitment: bool
    capacity_reprioritisation_allowed: bool

def deadline_guardian(d:DeadlineState)->Dict:
    projected=d.estimated_hours_to_finish+d.queue_delay_hours
    if projected <= d.remaining_hours:
        return {"status":"PASS","reason":"DELIVERY_TRAJECTORY_HEALTHY"}
    if d.capacity_reprioritisation_allowed:
        return {"status":"AUTO_NOTIFY","reason":"DEADLINE_RISK_REPRIORITISE_WITHIN_POLICY","projected_hours":projected}
    return {
        "status":"HUMAN_GATE",
        "reason":"ETA_REBASE_OR_COMMITMENT_REVIEW_REQUIRED",
        "contractual_commitment":d.contractual_commitment,
        "projected_hours":projected
    }

@dataclass(frozen=True)
class RouteCandidate:
    id: str
    supported: bool
    certified: bool
    quality_score: float
    reliability_score: float
    estimated_cost: float
    latency_score: float

def route_execution(candidates:List[RouteCandidate], min_quality:float, min_reliability:float)->Dict:
    eligible=[c for c in candidates if c.supported and c.certified and c.quality_score>=min_quality and c.reliability_score>=min_reliability]
    if not eligible:
        return {"status":"HUMAN_GATE","reason":"NO_ELIGIBLE_EXECUTION_PATH"}
    eligible=sorted(eligible,key=lambda c:(c.estimated_cost,-c.quality_score,-c.reliability_score,-c.latency_score,c.id))
    chosen=eligible[0]
    return {
        "status":"AUTO",
        "reason":"ELIGIBLE_PATH_SELECTED",
        "route_id":chosen.id,
        "selection_basis":"MIN_COST_AFTER_QUALITY_RELIABILITY_GATES",
        "production_authority":False
    }

@dataclass(frozen=True)
class LearningEvidence:
    evidence_complete: bool
    customer_accepted: bool
    actual_cost_known: bool
    rework_known: bool
    support_burden_known: bool

def learning_candidate(e:LearningEvidence)->Dict:
    if not e.evidence_complete or not e.actual_cost_known:
        return {"status":"HOLD","reason":"LEARNING_EVIDENCE_INCOMPLETE","policy_mutation_allowed":False}
    return {
        "status":"CANDIDATE_UPDATE",
        "reason":"VERIFIED_PROJECT_LEARNING_AVAILABLE",
        "candidate_targets":["DISCOVERY","PRICING","CAPABILITY_REGISTRY","CAPACITY_POLICY"],
        "customer_acceptance_signal":e.customer_accepted,
        "rework_signal_available":e.rework_known,
        "support_burden_signal_available":e.support_burden_known,
        "policy_mutation_allowed":False
    }

@dataclass(frozen=True)
class CommercialRecoveryState:
    event: str
    approved_contact_channel: bool
    consent_or_lawful_basis: bool
    attempts: int
    max_attempts: int

def commercial_recovery(c:CommercialRecoveryState)->Dict:
    allowed={"PAYMENT_FAILED","QUOTATION_EXPIRING","CUSTOMER_INACTIVE"}
    if c.event not in allowed:
        return {"status":"HUMAN_GATE","reason":"UNSUPPORTED_COMMERCIAL_RECOVERY_EVENT"}
    if not c.approved_contact_channel or not c.consent_or_lawful_basis:
        return {"status":"HUMAN_GATE","reason":"CONTACT_NOT_AUTHORISED"}
    if c.attempts >= c.max_attempts:
        return {"status":"HUMAN_GATE","reason":"FOLLOWUP_LIMIT_REACHED"}
    return {
        "status":"AUTO_NOTIFY",
        "reason":"POLICY_BOUNDED_COMMERCIAL_FOLLOWUP",
        "event":c.event,
        "charge_authority":False,
        "contract_mutation_authority":False,
        "compensation_authority":False
    }

@dataclass(frozen=True)
class ChangeImpact:
    material_change: bool
    scope_impact_known: bool
    cost_impact_known: bool
    time_impact_known: bool
    dependency_impact_known: bool
    risk_impact_known: bool
    regression_impact_known: bool

def change_impact_analysis(c:ChangeImpact)->Dict:
    if not c.material_change:
        return {"status":"REVIEW","reason":"MATERIALITY_UNCLEAR_OR_MINOR"}
    fields={
        "scope":c.scope_impact_known,
        "cost":c.cost_impact_known,
        "time":c.time_impact_known,
        "dependency":c.dependency_impact_known,
        "risk":c.risk_impact_known,
        "regression":c.regression_impact_known
    }
    missing=sorted(k for k,v in fields.items() if not v)
    if missing:
        return {"status":"IMPACT_REVIEW","reason":"CHANGE_IMPACT_INCOMPLETE","missing":missing,"approval_authority":False}
    return {
        "status":"READY_FOR_EXISTING_CHANGE_REQUEST_FLOW",
        "reason":"CHANGE_IMPACT_EVIDENCE_COMPLETE",
        "approval_authority":False
    }

@dataclass(frozen=True)
class CircuitSignals:
    security_signal: bool=False
    cost_spike: bool=False
    repeated_agent_loop: bool=False
    systemic_failure_count: int=0
    systemic_failure_threshold: int=3
    stale_hard_gate_evidence: bool=False

def circuit_breaker(s:CircuitSignals)->Dict:
    reasons=[]
    if s.security_signal: reasons.append("SECURITY_SIGNAL")
    if s.cost_spike: reasons.append("COST_SPIKE")
    if s.repeated_agent_loop: reasons.append("AGENT_LOOP")
    if s.systemic_failure_count>=s.systemic_failure_threshold: reasons.append("SYSTEMIC_FAILURE_THRESHOLD")
    if s.stale_hard_gate_evidence: reasons.append("STALE_HARD_GATE_EVIDENCE")
    if reasons:
        return {
            "status":"OPEN",
            "reason":"CIRCUIT_BREAKER_TRIGGERED",
            "triggers":sorted(reasons),
            "autonomous_actions_allowed":False,
            "reset_authority":"GOVERNED_REVIEW_REQUIRED"
        }
    return {"status":"CLOSED","reason":"NO_BREAKER_SIGNAL","autonomous_actions_allowed":True}
