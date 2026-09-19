#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class KickoffReadiness:
    approved_scope_snapshot: bool
    acceptance_criteria_confirmed: bool
    milestone_funding_evidence: bool
    customer_owner_assigned: bool
    ld_owner_assigned: bool
    communication_channel_confirmed: bool
    required_dependencies_ready: bool
    required_access_ready: bool
    environment_target_confirmed: bool
    data_handling_requirements_confirmed: bool
    kickoff_record_created: bool
    missing_customer_dependency: bool=False
    missing_ld_dependency: bool=False
    contradictory_evidence: bool=False

def assess(r:KickoffReadiness)->Dict:
    if r.contradictory_evidence:
        return {"status":"NOT_READY","reason":"CONTRADICTORY_READINESS_EVIDENCE","build_allowed":False}
    if r.missing_customer_dependency:
        return {"status":"CLIENT_ACTION_REQUIRED","reason":"CUSTOMER_DEPENDENCY_MISSING","build_allowed":False,"rebaseline_required":True}
    if r.missing_ld_dependency:
        return {"status":"LD_ACTION_REQUIRED","reason":"LD_DEPENDENCY_MISSING","build_allowed":False}
    checks={
      "approved_scope_snapshot":r.approved_scope_snapshot,
      "acceptance_criteria_confirmed":r.acceptance_criteria_confirmed,
      "milestone_funding_evidence":r.milestone_funding_evidence,
      "customer_owner_assigned":r.customer_owner_assigned,
      "ld_owner_assigned":r.ld_owner_assigned,
      "communication_channel_confirmed":r.communication_channel_confirmed,
      "required_dependencies_ready":r.required_dependencies_ready,
      "required_access_ready":r.required_access_ready,
      "environment_target_confirmed":r.environment_target_confirmed,
      "data_handling_requirements_confirmed":r.data_handling_requirements_confirmed,
      "kickoff_record_created":r.kickoff_record_created
    }
    missing=[k for k,v in checks.items() if not v]
    if missing:
        return {"status":"NOT_READY","reason":"READINESS_INCOMPLETE","missing":missing,"build_allowed":False}
    return {"status":"READY_FOR_KICKOFF","reason":"READINESS_COMPLETE","build_allowed":False}

def kickoff(readiness_status:str, human_kickoff_approved:bool)->Dict:
    if readiness_status!="READY_FOR_KICKOFF":
        return {"decision":"HOLD","reason":"READINESS_GATE_NOT_PASSED","build_allowed":False}
    if not human_kickoff_approved:
        return {"decision":"HOLD","reason":"HUMAN_KICKOFF_APPROVAL_REQUIRED","build_allowed":False}
    return {"decision":"KICKOFF","status":"KICKED_OFF","build_allowed":True,"production_authority":False}

def plaintext_secret_collection_allowed()->bool:
    return False
