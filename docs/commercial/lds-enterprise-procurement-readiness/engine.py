#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

HIGH_RISK_CLAIMS={"CERTIFICATION","INSURANCE","REGULATORY_APPROVAL","GOVERNMENT_APPROVAL"}

@dataclass(frozen=True)
class ProcurementEvidence:
    evidence_present:bool
    evidence_current:bool
    claim_type:str
    customer_specific_commitment:bool=False
    policy_version:str=""

def assess(x:ProcurementEvidence)->Dict:
    flags=[]
    if not x.evidence_present:
        return {"status":"NEED_EVIDENCE","claim_status":"UNSUPPORTED","risk_flags":["EVIDENCE_MISSING"],"contractual_commitment_authorized":False}
    if not x.evidence_current:
        flags.append("EVIDENCE_STALE")
    if x.claim_type in HIGH_RISK_CLAIMS and not x.evidence_current:
        flags.append("HIGH_RISK_CLAIM_NOT_CURRENT")
    if x.customer_specific_commitment:
        flags.append("HUMAN_CONTRACT_REVIEW_REQUIRED")
    if not x.policy_version:
        flags.append("POLICY_VERSION_REQUIRED")
    return {
      "status":"READY_FOR_HUMAN_PROCUREMENT_REVIEW" if not flags else "REVIEW",
      "claim_status":"EVIDENCE_BACKED" if x.evidence_current else "NOT_CURRENT",
      "risk_flags":flags,
      "contractual_commitment_authorized":False
    }

def unsupported_claim_allowed()->bool:
    return False
