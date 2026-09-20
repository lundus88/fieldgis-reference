#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

VALID_PLANS={"ESSENTIAL_CARE","BUSINESS_CARE","MANAGED_SYSTEM"}

@dataclass(frozen=True)
class SupportPlan:
    plan_key:str
    commercially_approved:bool
    response_target_evidenced:bool
    resolution_target_evidenced:bool
    recurring_price_approved:bool
    customer_accepted:bool
    third_party_costs_disclosed:bool
    cancellation_terms_disclosed:bool

def assess(plan:SupportPlan)->Dict:
    if plan.plan_key not in VALID_PLANS:
        return {"status":"HOLD","reason":"UNKNOWN_PLAN"}
    if not plan.commercially_approved:
        return {"status":"HOLD","reason":"PLAN_NOT_COMMERCIALLY_APPROVED"}
    if not plan.third_party_costs_disclosed:
        return {"status":"HOLD","reason":"THIRD_PARTY_COST_DISCLOSURE_REQUIRED"}
    if not plan.cancellation_terms_disclosed:
        return {"status":"HOLD","reason":"CANCELLATION_TERMS_REQUIRED"}
    if not plan.recurring_price_approved:
        return {"status":"HOLD","reason":"RECURRING_PRICE_NOT_APPROVED"}
    if not plan.customer_accepted:
        return {"status":"CUSTOMER_DECISION","activation_allowed":False}
    return {
      "status":"READY_FOR_ACTIVATION_REVIEW",
      "activation_allowed":False,
      "advertise_response_target":plan.response_target_evidenced,
      "advertise_resolution_target":plan.resolution_target_evidenced
    }

def classify_request(within_support:bool, defect:bool, security_incident:bool, enhancement:bool)->Dict:
    if security_incident:
        return {"route":"HUMAN_SECURITY_ESCALATION","billable_enhancement":False}
    if defect:
        return {"route":"WARRANTY_OR_REMEDIATION_REVIEW","billable_enhancement":False}
    if within_support:
        return {"route":"SUPPORT_QUEUE","billable_enhancement":False}
    if enhancement:
        return {"route":"CHANGE_REQUEST_OR_NEW_QUOTE","billable_enhancement":True}
    return {"route":"MANUAL_REVIEW","billable_enhancement":False}
