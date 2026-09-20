#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class IncidentEvidence:
    policy_version:str
    severity:str
    response_minutes:int
    resolution_minutes:int
    target_response_minutes:int
    target_resolution_minutes:int
    monitoring_current:bool
    customer_impact_confirmed:bool

def assess(e:IncidentEvidence)->Dict:
    if not e.policy_version:
        return {"status":"REVIEW","risk_flags":["SLA_POLICY_REQUIRED"],"service_credit_authorized":False}
    if e.severity not in {"SEV1","SEV2","SEV3","SEV4"}:
        return {"status":"REVIEW","risk_flags":["INVALID_SEVERITY"],"service_credit_authorized":False}
    flags=[]
    if not e.monitoring_current: flags.append("MONITORING_EVIDENCE_STALE_OR_MISSING")
    if not e.customer_impact_confirmed: flags.append("CUSTOMER_IMPACT_NOT_CONFIRMED")
    response="MET" if e.response_minutes<=e.target_response_minutes else "BREACHED"
    resolution="MET" if e.resolution_minutes<=e.target_resolution_minutes else "BREACHED"
    if response=="BREACHED": flags.append("RESPONSE_TARGET_BREACH")
    if resolution=="BREACHED": flags.append("RESOLUTION_TARGET_BREACH")
    return {
      "status":"EVIDENCE_READY_FOR_HUMAN_REVIEW" if e.monitoring_current else "REVIEW",
      "response_status":response,
      "resolution_status":resolution,
      "risk_flags":flags,
      "service_credit_authorized":False,
      "human_review_required":True
    }

def automatic_service_credit_allowed()->bool:
    return False
