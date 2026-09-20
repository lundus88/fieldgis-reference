#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Tuple,Dict

@dataclass(frozen=True)
class PricingEvidence:
    scope_approved: bool
    estimated_delivery_cost_minor: int
    third_party_one_time_minor: int=0
    comparable_project_count: int=0
    historical_rework_rate_pct: float=0.0
    historical_support_burden_pct: float=0.0
    target_margin_pct: float=35.0
    risk_contingency_pct: float=10.0
    inputs_current: bool=True
    capacity_pressure: bool=False
    contradictory_evidence: bool=False

def confidence(e:PricingEvidence)->str:
    if e.contradictory_evidence or not e.inputs_current:
        return "LOW"
    if e.comparable_project_count >= 8:
        return "HIGH"
    if e.comparable_project_count >= 3:
        return "MEDIUM"
    return "LOW"

def estimate(e:PricingEvidence)->Dict:
    if not e.scope_approved:
        return {"status":"INSUFFICIENT_EVIDENCE","reason":"APPROVED_SCOPE_REQUIRED"}
    if e.estimated_delivery_cost_minor < 0 or e.third_party_one_time_minor < 0:
        return {"status":"REVIEW","reason":"INVALID_COST_INPUT"}
    if e.contradictory_evidence:
        return {"status":"REVIEW","reason":"CONTRADICTORY_EVIDENCE"}
    if not e.inputs_current:
        return {"status":"REVIEW","reason":"STALE_OR_INCOMPLETE_COST_EVIDENCE"}

    base=e.estimated_delivery_cost_minor + e.third_party_one_time_minor
    learning_load=max(0.0,e.historical_rework_rate_pct)+max(0.0,e.historical_support_burden_pct)
    contingency=max(0.0,e.risk_contingency_pct)+min(learning_load,30.0)
    if e.capacity_pressure:
        contingency += 5.0

    cost_floor=round(base*(1+contingency/100))
    margin=max(0.0,min(e.target_margin_pct,80.0))/100.0
    if margin>=1:
        return {"status":"REVIEW","reason":"INVALID_MARGIN_POLICY"}
    center=round(cost_floor/(1-margin)) if margin < 1 else cost_floor

    conf=confidence(e)
    spread={"HIGH":0.08,"MEDIUM":0.15,"LOW":0.25}[conf]
    low=round(center*(1-spread))
    high=round(center*(1+spread))

    status="READY_FOR_HUMAN_PRICING_REVIEW" if conf in {"HIGH","MEDIUM"} else "INSUFFICIENT_EVIDENCE"
    return {
      "status":status,
      "evidence_confidence":conf,
      "estimated_cost_floor_minor":cost_floor,
      "internal_price_range_low_minor":low,
      "internal_price_range_high_minor":high,
      "customer_price_authorized":False,
      "auto_quote":False,
      "auto_publish":False
    }

def factory_credit_to_customer_price_allowed()->bool:
    return False
