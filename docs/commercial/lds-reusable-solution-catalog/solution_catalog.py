#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Tuple,Dict

STATES={"EXPERIMENTAL","VALIDATED","PRODUCTION_PROVEN","DEPRECATED"}

@dataclass(frozen=True)
class Component:
    component_key:str
    version:str
    state:str
    compatible_builders:Tuple[str,...]
    security_current:bool
    regression_current:bool
    repeatable_success_runs:int
    production_projects:int
    provenance_complete:bool
    licensing_clear:bool
    known_critical_issue:bool=False

def evaluate(c:Component,builder_key:str)->Dict:
    if c.state not in STATES:
        return {"status":"HOLD","reason":"UNKNOWN_COMPONENT_STATE"}
    if c.state=="DEPRECATED":
        return {"status":"HOLD","reason":"COMPONENT_DEPRECATED"}
    if builder_key not in c.compatible_builders:
        return {"status":"HOLD","reason":"BUILDER_INCOMPATIBLE"}
    if not c.provenance_complete or not c.licensing_clear:
        return {"status":"REVIEW","reason":"PROVENANCE_OR_LICENSING_INCOMPLETE"}
    if not c.security_current or not c.regression_current:
        return {"status":"REVIEW","reason":"STALE_SECURITY_OR_REGRESSION_EVIDENCE"}
    if c.known_critical_issue:
        return {"status":"HOLD","reason":"KNOWN_CRITICAL_ISSUE"}
    if c.state=="PRODUCTION_PROVEN" and (c.production_projects<2 or c.repeatable_success_runs<3):
        return {"status":"REVIEW","reason":"INSUFFICIENT_PRODUCTION_PROOF"}
    confidence={
      "EXPERIMENTAL":"LOW",
      "VALIDATED":"MEDIUM",
      "PRODUCTION_PROVEN":"HIGH"
    }[c.state]
    return {
      "status":"REUSE_CANDIDATE",
      "reuse_confidence":confidence,
      "build_authorized":False,
      "production_authorized":False
    }

def compose(components:Tuple[Component,...],builder_key:str)->Dict:
    results=[evaluate(c,builder_key) for c in components]
    if any(r["status"]=="HOLD" for r in results):
        return {"status":"HOLD","components":results}
    if any(r["status"]=="REVIEW" for r in results):
        return {"status":"REVIEW","components":results}
    return {"status":"COMPOSITION_CANDIDATE","components":results,"build_authorized":False}
