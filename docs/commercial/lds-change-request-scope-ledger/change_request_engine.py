#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class ChangeRequest:
    material_change: bool
    within_original_scope: bool
    defect_or_rework: bool
    cost_impact_known: bool
    time_impact_known: bool
    customer_approved: bool
    human_commercial_approved: bool
    evidence_complete: bool
    base_scope_version: int

def assess(cr:ChangeRequest)->Dict:
    if cr.base_scope_version < 1:
        return {"state":"HOLD","reason":"INVALID_BASE_SCOPE_VERSION"}
    if cr.within_original_scope or cr.defect_or_rework:
        return {
            "state":"NO_CHANGE_REQUEST_REQUIRED",
            "billable_change":False,
            "reason":"ORIGINAL_SCOPE_OR_REMEDIATION"
        }
    if not cr.material_change:
        return {"state":"REVIEW","reason":"MATERIALITY_UNCLEAR"}
    if not cr.evidence_complete:
        return {"state":"REVIEW","reason":"EVIDENCE_INCOMPLETE"}
    if not cr.cost_impact_known or not cr.time_impact_known:
        return {"state":"IMPACT_REVIEW","reason":"COMMERCIAL_OR_SCHEDULE_IMPACT_UNKNOWN"}
    if not cr.customer_approved:
        return {"state":"CUSTOMER_DECISION","build_allowed":False}
    if not cr.human_commercial_approved:
        return {"state":"APPROVAL_PENDING","build_allowed":False}
    return {
        "state":"APPROVED",
        "build_allowed":True,
        "new_scope_version":cr.base_scope_version+1,
        "preserve_prior_scope":True
    }

def apply_change(current_state:str, new_scope_version:int)->Dict:
    if current_state!="APPROVED":
        return {"decision":"HOLD","reason":"APPROVED_CHANGE_REQUIRED"}
    if new_scope_version<2:
        return {"decision":"HOLD","reason":"INVALID_NEW_SCOPE_VERSION"}
    return {"decision":"APPLY","state":"APPLIED","scope_version":new_scope_version}

def can_silently_modify_quote()->bool:
    return False
