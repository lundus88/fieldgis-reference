#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Tuple,Dict

@dataclass(frozen=True)
class Dependency:
    provider_key:str
    project_ids:Tuple[str,...]
    criticality:str
    fallback_available:bool
    fallback_verified:bool
    owner_known:bool
    evidence_current:bool
    provider_healthy:bool

def assess(d:Dependency)->Dict:
    if not d.project_ids:
        return {"status":"REVIEW","reason":"AFFECTED_PROJECTS_UNKNOWN"}
    if not d.owner_known:
        return {"status":"REVIEW","reason":"DEPENDENCY_OWNER_UNKNOWN"}
    if not d.evidence_current:
        return {"status":"REVIEW","reason":"STALE_DEPENDENCY_EVIDENCE"}
    if not d.provider_healthy:
        if d.criticality in {"CRITICAL","HIGH"} and not d.fallback_verified:
            return {
              "status":"HOLD",
              "reason":"HIGH_IMPACT_PROVIDER_OUTAGE_WITHOUT_VERIFIED_FALLBACK",
              "affected_projects":list(d.project_ids),
              "auto_failover":False,
              "auto_customer_contact":False
            }
        return {
          "status":"HUMAN_REVIEW",
          "reason":"PROVIDER_OUTAGE",
          "affected_projects":list(d.project_ids),
          "auto_failover":False,
          "auto_customer_contact":False
        }
    if d.criticality in {"CRITICAL","HIGH"} and d.fallback_available and not d.fallback_verified:
        return {"status":"REVIEW","reason":"FALLBACK_NOT_VERIFIED"}
    return {"status":"CURRENT","reason":"DEPENDENCY_EVIDENCE_CURRENT"}

def can_auto_switch_provider()->bool:
    return False
