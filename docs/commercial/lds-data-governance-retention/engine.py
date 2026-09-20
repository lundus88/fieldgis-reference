#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class DataDecision:
    policy_version:str
    data_class:str
    record_age_days:int
    retention_days:int
    deletion_request:bool=False
    legal_hold:bool=False
    export_request:bool=False
    identity_authorized:bool=False

def assess(x:DataDecision)->Dict:
    if not x.policy_version:
        return {"status":"REVIEW","risk_flags":["RETENTION_POLICY_REQUIRED"],"destructive_deletion_authorized":False}
    if x.retention_days < 0 or x.record_age_days < 0:
        return {"status":"REVIEW","risk_flags":["INVALID_RETENTION_INPUT"],"destructive_deletion_authorized":False}
    flags=[]
    retention="RETAIN" if x.record_age_days < x.retention_days else "RETENTION_ELIGIBLE_FOR_REVIEW"
    deletion="NOT_REQUESTED"
    if x.deletion_request:
        if x.legal_hold:
            deletion="BLOCKED_BY_LEGAL_HOLD"
            flags.append("LEGAL_HOLD_ACTIVE")
        else:
            deletion="ELIGIBLE_FOR_HUMAN_DELETION_REVIEW"
    export="NOT_REQUESTED"
    if x.export_request:
        export="ELIGIBLE_FOR_HUMAN_EXPORT_REVIEW" if x.identity_authorized else "BLOCKED_IDENTITY_OR_ORG_AUTH_REQUIRED"
        if not x.identity_authorized:
            flags.append("EXPORT_AUTHORIZATION_MISSING")
    return {
      "status":"EVIDENCE_READY_FOR_HUMAN_REVIEW",
      "retention_status":retention,
      "deletion_status":deletion,
      "export_status":export,
      "risk_flags":flags,
      "destructive_deletion_authorized":False,
      "bulk_export_authorized":False
    }

def automatic_destructive_deletion_allowed()->bool:
    return False
