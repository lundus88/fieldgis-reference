#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class Usage:
    quantity:float
    unit_cost_minor:float
    evidence_current:bool
    tenant_match:bool
    billing_policy_version:str

def assess(u:Usage)->Dict:
    if u.quantity < 0 or u.unit_cost_minor < 0:
        return {"status":"REVIEW","risk_flags":["INVALID_USAGE_INPUT"],"customer_charge_authorized":False}
    if not u.tenant_match:
        return {"status":"HOLD","risk_flags":["TENANT_MISMATCH"],"customer_charge_authorized":False}
    flags=[]
    if not u.evidence_current: flags.append("USAGE_EVIDENCE_STALE_OR_MISSING")
    if not u.billing_policy_version: flags.append("BILLING_POLICY_REQUIRED")
    cost=round(u.quantity*u.unit_cost_minor)
    return {
      "status":"INTERNAL_COST_READY" if not flags else "REVIEW",
      "internal_cost_minor":cost,
      "risk_flags":flags,
      "billing_candidate":False,
      "customer_charge_authorized":False
    }

def internal_cost_is_customer_price()->bool:
    return False
