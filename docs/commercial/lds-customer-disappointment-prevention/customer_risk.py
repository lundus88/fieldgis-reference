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


def assess_account_continuity(
    customer_runtime_independent:bool,
    grace_recovery_available:bool,
    human_access_escalation_available:bool
)->Dict:
    safe=all([customer_runtime_independent,grace_recovery_available,human_access_escalation_available])
    return {
        "risk_id":"CDP-027",
        "active":not safe,
        "severity":"P0" if not safe else "P3",
        "action":"PROTECT_RUNTIME_AND_HUMAN_ESCALATE" if not safe else "ALLOW"
    }

def assess_persisted_state(
    project_state_persisted:bool,
    decision_ledger_present:bool,
    checkpoint_present:bool
)->Dict:
    safe=all([project_state_persisted,decision_ledger_present,checkpoint_present])
    return {
        "risk_id":"CDP-028",
        "active":not safe,
        "severity":"P1" if not safe else "P3",
        "action":"BLOCK_CONTEXT_DEPENDENT_CONTINUATION" if not safe else "ALLOW"
    }

def assess_destructive_action(
    snapshot_present:bool,
    target_confirmed:bool,
    blast_radius_checked:bool,
    rollback_evidence_present:bool,
    human_gate_required:bool,
    human_gate_approved:bool
)->Dict:
    gate_ok=(not human_gate_required) or human_gate_approved
    safe=all([snapshot_present,target_confirmed,blast_radius_checked,rollback_evidence_present,gate_ok])
    return {
        "risk_id":"CDP-029",
        "active":not safe,
        "severity":"P0" if not safe else "P3",
        "action":"BLOCK_DESTRUCTIVE_ACTION" if not safe else "ALLOW"
    }

def assess_domain_readiness(
    dns_verified:bool,
    ssl_active:bool,
    https_health_pass:bool,
    mail_auth_required:bool=False,
    mail_auth_pass:bool=False
)->Dict:
    ready=dns_verified and ssl_active and https_health_pass and ((not mail_auth_required) or mail_auth_pass)
    return {
        "risk_id":"CDP-030",
        "active":not ready,
        "severity":"P1" if not ready else "P3",
        "action":"BLOCK_READY_CLAIM" if not ready else "ALLOW"
    }

def assess_permission_preflight(permissions:Dict[str,bool])->Dict:
    required={"edit","approve","deploy","billing_admin","admin","accept"}
    missing=sorted(k for k in required if not permissions.get(k,False))
    return {
        "risk_id":"CDP-031",
        "active":bool(missing),
        "severity":"P1" if missing else "P3",
        "missing":missing,
        "action":"BLOCK_KICKOFF_OR_RELEASE" if missing else "ALLOW"
    }

def assess_plan_change(
    changed:bool,
    change_record_present:bool,
    effective_date_present:bool,
    notice_required:bool,
    notice_sent:bool
)->Dict:
    safe=(not changed) or (change_record_present and effective_date_present and ((not notice_required) or notice_sent))
    return {
        "risk_id":"CDP-032",
        "active":not safe,
        "severity":"P1" if not safe else "P3",
        "action":"BLOCK_COMMERCIAL_CHANGE" if not safe else "ALLOW"
    }

def assess_support_triage(
    severity:str,
    bot_only:bool,
    no_progress_responses:int
)->Dict:
    if severity not in {"P0","P1","P2","P3"} or no_progress_responses < 0:
        raise ValueError("invalid support triage")
    escalate=(severity in {"P0","P1"} and bot_only) or no_progress_responses >= 2
    return {
        "risk_id":"CDP-033",
        "active":escalate,
        "severity":"P1" if escalate else "P3",
        "action":"HUMAN_ESCALATION" if escalate else "CONTINUE"
    }

def assess_idempotency(
    consequential:bool,
    idempotency_key_present:bool,
    dedupe_guard_present:bool,
    side_effect_ledger_present:bool
)->Dict:
    safe=(not consequential) or all([idempotency_key_present,dedupe_guard_present,side_effect_ledger_present])
    return {
        "risk_id":"CDP-034",
        "active":not safe,
        "severity":"P0" if not safe else "P3",
        "action":"BLOCK_SIDE_EFFECT" if not safe else "ALLOW"
    }

def assess_asset_ownership(
    business_or_client_owned:bool,
    designated_admin_present:bool,
    recovery_contact_present:bool,
    ownership_record_present:bool
)->Dict:
    safe=all([business_or_client_owned,designated_admin_present,recovery_contact_present,ownership_record_present])
    return {
        "risk_id":"CDP-035",
        "active":not safe,
        "severity":"P1" if not safe else "P3",
        "action":"BLOCK_FINAL_OPERATIONAL_HANDOVER" if not safe else "ALLOW"
    }

def assess_offboarding(
    export_complete:bool,
    migration_complete:bool,
    retention_window_known:bool,
    customer_copy_confirmed:bool
)->Dict:
    safe=all([export_complete,migration_complete,retention_window_known,customer_copy_confirmed])
    return {
        "risk_id":"CDP-036",
        "active":not safe,
        "severity":"P1" if not safe else "P3",
        "action":"BLOCK_TERMINATION_OR_DESTRUCTIVE_OFFBOARDING" if not safe else "ALLOW"
    }
