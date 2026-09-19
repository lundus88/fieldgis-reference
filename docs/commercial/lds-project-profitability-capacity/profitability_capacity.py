#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict,Optional

@dataclass(frozen=True)
class ProjectEconomics:
    revenue_minor:int
    provider_fees_minor:int=0
    hosting_minor:int=0
    ai_api_minor:int=0
    third_party_minor:int=0
    factory_runtime_minor:int=0
    human_effort_minor:int=0
    support_minor:int=0
    rework_minor:int=0
    refund_credit_minor:int=0
    inputs_current:bool=True

@dataclass(frozen=True)
class Capacity:
    active_projects:int
    concurrent_builds:int
    support_load:int
    critical_incidents:int
    available_units:int
    reserved_units:int
    requested_units:int
    resource_pressure:bool=False

def profitability(e:ProjectEconomics)->Dict:
    if e.revenue_minor < 0:
        return {"status":"REVIEW","reason":"INVALID_REVENUE"}
    if not e.inputs_current:
        return {"status":"REVIEW","reason":"STALE_OR_UNKNOWN_COST_INPUT"}
    total=sum([
      e.provider_fees_minor,e.hosting_minor,e.ai_api_minor,e.third_party_minor,
      e.factory_runtime_minor,e.human_effort_minor,e.support_minor,
      e.rework_minor,e.refund_credit_minor
    ])
    contribution=e.revenue_minor-total
    margin_pct=None if e.revenue_minor==0 else round((contribution/e.revenue_minor)*100,2)
    if e.revenue_minor==0:
        status="REVIEW"
    elif contribution < 0:
        status="AT_RISK"
    elif margin_pct is not None and margin_pct < 20:
        status="REVIEW"
    else:
        status="HEALTHY"
    return {
      "status":status,
      "revenue_minor":e.revenue_minor,
      "total_cost_minor":total,
      "contribution_minor":contribution,
      "margin_pct":margin_pct,
      "auto_price_change":False,
      "auto_customer_reject":False
    }

def capacity_decision(c:Capacity)->Dict:
    effective=max(0,c.available_units-c.reserved_units)
    if c.critical_incidents>0:
        return {"status":"HOLD_CAPACITY","reason":"CRITICAL_INCIDENT_RESERVE","schedulable":False}
    if c.resource_pressure:
        return {"status":"HOLD_CAPACITY","reason":"RESOURCE_PRESSURE","schedulable":False}
    if c.requested_units>effective:
        return {"status":"HOLD_CAPACITY","reason":"INSUFFICIENT_AVAILABLE_CAPACITY","schedulable":False}
    if c.support_load>=80:
        return {"status":"REVIEW","reason":"HIGH_SUPPORT_LOAD","schedulable":False}
    return {"status":"HEALTHY","reason":"CAPACITY_AVAILABLE","schedulable":True}

def commercial_action(profit_status:str,capacity_status:str)->Dict:
    if capacity_status=="HOLD_CAPACITY":
        return {"decision":"HUMAN_REVIEW","allowed_action":"REBASE_SCHEDULE_OR_WAITLIST"}
    if profit_status in {"AT_RISK","REVIEW"}:
        return {"decision":"HUMAN_REVIEW","allowed_action":"RESCOPE_REPRICE_OR_ACCEPT_WITH_RATIONALE"}
    return {"decision":"PROCEED_TO_EXISTING_COMMERCIAL_GATES","automatic_commitment":False}
