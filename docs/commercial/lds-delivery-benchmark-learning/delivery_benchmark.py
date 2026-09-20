#!/usr/bin/env python3
from dataclasses import dataclass
from statistics import median
from typing import Tuple,Dict

@dataclass(frozen=True)
class DeliveryRecord:
    project_class:str
    first_visible_days:float
    delivery_days:float
    internal_cost_minor:int
    rework_pct:float
    support_burden_pct:float
    dependency_delay_days:float
    uat_cycle_days:float
    evidence_current:bool=True

def summarize(records:Tuple[DeliveryRecord,...],project_class:str)->Dict:
    comparable=[r for r in records if r.project_class==project_class]
    if len(comparable)<3:
        return {"status":"INSUFFICIENT_EVIDENCE","sample_size":len(comparable)}
    if any(not r.evidence_current for r in comparable):
        return {"status":"REVIEW","reason":"STALE_HISTORICAL_EVIDENCE","sample_size":len(comparable)}

    def spread(vals):
        vals=sorted(vals)
        return {"min":vals[0],"median":median(vals),"max":vals[-1]}

    confidence="HIGH" if len(comparable)>=8 else "MEDIUM"
    return {
      "status":"BENCHMARK_READY",
      "project_class":project_class,
      "sample_size":len(comparable),
      "confidence":confidence,
      "first_visible_progress_days":spread([r.first_visible_days for r in comparable]),
      "delivery_cycle_days":spread([r.delivery_days for r in comparable]),
      "internal_cost_minor":spread([r.internal_cost_minor for r in comparable]),
      "rework_pct":spread([r.rework_pct for r in comparable]),
      "support_burden_pct":spread([r.support_burden_pct for r in comparable]),
      "dependency_delay_days":spread([r.dependency_delay_days for r in comparable]),
      "uat_cycle_days":spread([r.uat_cycle_days for r in comparable]),
      "auto_customer_eta":False,
      "auto_reprice":False
    }

def can_overwrite_approved_commitment()->bool:
    return False
