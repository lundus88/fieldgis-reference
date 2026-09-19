#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List

SEVERITY_ORDER={"P3":0,"P2":1,"P1":2,"P0":3}

@dataclass(frozen=True)
class Signal:
    risk_id: str
    severity: str
    active: bool
    evidence_refs: tuple[str,...]=()
    customer_impact: bool=True

def evaluate(signals: List[Signal]) -> Dict:
    active=[s for s in signals if s.active]
    if not active:
        return {"status":"CLEAR","highest_severity":None,"actions":[]}

    for s in active:
        if s.severity not in SEVERITY_ORDER:
            raise ValueError("invalid severity")
        if not s.evidence_refs:
            return {
                "status":"HOLD",
                "highest_severity":s.severity,
                "actions":["COLLECT_EVIDENCE"],
                "reason":"ACTIVE_RISK_WITHOUT_EVIDENCE"
            }

    highest=max(active,key=lambda s:SEVERITY_ORDER[s.severity]).severity
    actions=[]
    if highest=="P0":
        actions += ["HUMAN_ESCALATION","CONTAIN_IF_APPLICABLE","CLIENT_STATUS_UPDATE"]
    elif highest=="P1":
        actions += ["OWNER_ASSIGN","MITIGATION_PLAN","CLIENT_STATUS_UPDATE"]
    elif highest=="P2":
        actions += ["PROACTIVE_UPDATE","CORRECT_WORKFLOW"]
    else:
        actions += ["TRACK"]

    if any(s.risk_id=="CDP-004" for s in active):
        actions += ["SET_CLIENT_ACTION_REQUIRED","REBASELINE_ETA"]
    if any(s.risk_id in {"CDP-008","CDP-010"} for s in active):
        actions += ["FREEZE_CONSEQUENTIAL_AUTOMATION"]

    return {
        "status":"AT_RISK" if highest in {"P0","P1"} else "WATCH",
        "highest_severity":highest,
        "actions":sorted(set(actions))
    }

def should_send_status(last_update_business_hours:int, active_risk:bool)->bool:
    if last_update_business_hours < 0:
        raise ValueError("invalid hours")
    if active_risk:
        return last_update_business_hours >= 4
    return last_update_business_hours >= 24


def detect_silent_dissatisfaction(
    pulse_status:str,
    reopened_tickets:int,
    repeat_followups:int
)->Dict:
    allowed={"SATISFIED","MINOR_ISSUE","NEED_ATTENTION","NO_RESPONSE"}
    if pulse_status not in allowed:
        raise ValueError("invalid pulse status")
    if reopened_tickets < 0 or repeat_followups < 0:
        raise ValueError("invalid count")
    active = (
        pulse_status=="NEED_ATTENTION"
        or reopened_tickets >= 2
        or repeat_followups >= 2
    )
    return {
        "risk_id":"CDP-017",
        "active":active,
        "severity":"P1" if active else "P3",
        "action":"PROACTIVE_FOLLOWUP" if active else "TRACK"
    }

def detect_handoff_context_loss(
    owner_changed:bool,
    context_record_present:bool,
    customer_repeat_required:bool
)->Dict:
    active = owner_changed and (not context_record_present or customer_repeat_required)
    return {
        "risk_id":"CDP-018",
        "active":active,
        "severity":"P1" if active else "P3",
        "action":"RESTORE_CONTEXT_BEFORE_REPLY" if active else "TRACK"
    }

def assess_support_sla(
    first_response_hours:float,
    first_response_target_hours:float,
    resolution_hours:float,
    resolution_target_hours:float,
    resolved:bool
)->Dict:
    vals=[first_response_hours,first_response_target_hours,resolution_hours,resolution_target_hours]
    if any(v < 0 for v in vals) or first_response_target_hours == 0 or resolution_target_hours == 0:
        raise ValueError("invalid SLA values")
    response_met = first_response_hours <= first_response_target_hours
    resolution_met = resolved and resolution_hours <= resolution_target_hours
    active = (not response_met) or (not resolution_met)
    return {
        "risk_id":"CDP-019" if response_met and not resolution_met else "CDP-007",
        "active":active,
        "response_sla_met":response_met,
        "resolution_sla_met":resolution_met,
        "action":"ESCALATE_RESOLUTION" if response_met and not resolution_met else ("ESCALATE_SUPPORT" if active else "CLOSE")
    }

def detect_adoption_failure(
    uat_passed:bool,
    quick_start_completed:bool,
    core_workflow_used:bool,
    how_to_queries:int
)->Dict:
    if how_to_queries < 0:
        raise ValueError("invalid query count")
    active = uat_passed and (
        not quick_start_completed
        or not core_workflow_used
        or how_to_queries >= 3
    )
    return {
        "risk_id":"CDP-015",
        "active":active,
        "severity":"P2" if active else "P3",
        "action":"ADOPTION_CHECKPOINT" if active else "TRACK"
    }


def assess_cost_surprise(
    approved_amount:float,
    proposed_amount:float,
    approved_change_request:bool
)->Dict:
    if approved_amount < 0 or proposed_amount < 0:
        raise ValueError("invalid amount")
    extra = proposed_amount > approved_amount
    active = extra and not approved_change_request
    return {
        "risk_id":"CDP-020",
        "active":active,
        "severity":"P1" if active else "P3",
        "action":"BLOCK_EXTRA_CHARGE" if active else "ALLOW_WITHIN_APPROVAL"
    }

def verify_delivery_success(
    deploy_command_ok:bool,
    health_check_ok:bool,
    artifact_id_present:bool,
    rollback_ref_present:bool
)->Dict:
    complete = all([deploy_command_ok,health_check_ok,artifact_id_present,rollback_ref_present])
    return {
        "risk_id":"CDP-021",
        "active":not complete,
        "severity":"P1" if not complete else "P3",
        "delivery_complete":complete,
        "action":"BLOCK_COMPLETE_CLAIM" if not complete else "ALLOW_DELIVERY_CANDIDATE"
    }

def assess_update_regression(
    version_pinned:bool,
    compatibility_pass:bool,
    regression_pass:bool
)->Dict:
    safe = version_pinned and compatibility_pass and regression_pass
    return {
        "risk_id":"CDP-022",
        "active":not safe,
        "severity":"P1" if not safe else "P3",
        "action":"BLOCK_UPDATED_TOOL_FOR_CUSTOMER_DELIVERY" if not safe else "ALLOW"
    }

def reconcile_state(states:Dict[str,str], authoritative_source:str)->Dict:
    if authoritative_source not in states:
        raise ValueError("authoritative source missing")
    authoritative=states[authoritative_source]
    conflict=any(v != authoritative for v in states.values())
    return {
        "risk_id":"CDP-023",
        "active":conflict,
        "severity":"P1" if conflict else "P3",
        "authoritative_state":authoritative,
        "action":"FAIL_CLOSED_AND_RECONCILE" if conflict else "ALLOW"
    }

def assess_agent_budget(
    steps:int,max_steps:int,
    retries:int,max_retries:int,
    cost:float,max_cost:float,
    wall_clock_minutes:float,max_wall_clock_minutes:float,
    repeated_identical_failure:bool
)->Dict:
    vals=[steps,max_steps,retries,max_retries]
    if any(v < 0 for v in vals) or min(max_steps,max_retries) == 0:
        raise ValueError("invalid execution budget")
    if cost < 0 or max_cost <= 0 or wall_clock_minutes < 0 or max_wall_clock_minutes <= 0:
        raise ValueError("invalid execution budget")
    exceeded = (
        steps > max_steps or retries > max_retries or cost > max_cost
        or wall_clock_minutes > max_wall_clock_minutes or repeated_identical_failure
    )
    return {
        "risk_id":"CDP-024",
        "active":exceeded,
        "severity":"P1" if exceeded else "P3",
        "action":"KILL_AND_HOLD" if exceeded else "CONTINUE"
    }

def assess_portability(
    ownership_defined:bool,
    agreed_export_available:bool,
    agreed_source_handover_available:bool,
    exit_docs_present:bool
)->Dict:
    ready=all([ownership_defined,agreed_export_available,agreed_source_handover_available,exit_docs_present])
    return {
        "risk_id":"CDP-025",
        "active":not ready,
        "severity":"P1" if not ready else "P3",
        "action":"BLOCK_FINAL_HANDOVER" if not ready else "ALLOW"
    }

def assess_internal_failure_charge(
    internal_failure:bool,
    proposed_extra_charge:bool,
    genuine_scope_change:bool,
    human_change_approval:bool
)->Dict:
    forbidden = internal_failure and proposed_extra_charge and not (genuine_scope_change and human_change_approval)
    return {
        "risk_id":"CDP-026",
        "active":forbidden,
        "severity":"P0" if forbidden else "P3",
        "action":"BLOCK_CHARGE_AND_HUMAN_REVIEW" if forbidden else "ALLOW"
    }
