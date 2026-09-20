#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class Assessment:
    business_type:str
    problem_statement:str
    current_workflow:str
    desired_outcome:str
    current_tools:str=""
    budget_band:str="Not sure yet"
    timeline:str="Later / exploring"
    geo_signal:bool=False
    ai_signal:bool=False
    regulated_or_high_risk:bool=False
    scope_unclear:bool=False

def classify(a:Assessment)->Dict:
    if a.regulated_or_high_risk:
        return {"classification":"MANUAL_REVIEW","status":"MANUAL_REVIEW","reason":"HIGH_RISK_OR_REGULATED"}
    if not a.problem_statement.strip() or not a.current_workflow.strip() or not a.desired_outcome.strip():
        return {"classification":"MANUAL_REVIEW","status":"NEED_MORE_INFO","reason":"CORE_CONTEXT_MISSING"}
    if a.scope_unclear:
        return {"classification":"CUSTOM_COMPLEX","status":"NEED_MORE_INFO","reason":"SCOPE_NOT_BOUNDED"}
    if a.geo_signal:
        return {"classification":"GEO_AI_SOLUTION","status":"QUALIFIED","reason":"GEOSPATIAL_WORKFLOW_SIGNAL"}
    if a.ai_signal:
        return {"classification":"GEO_AI_SOLUTION","status":"QUALIFIED","reason":"AI_ASSISTED_WORKFLOW_SIGNAL"}
    text=" ".join([a.problem_statement,a.current_workflow,a.desired_outcome,a.current_tools]).lower()
    quick_terms=["quotation","report","reminder","follow-up","pdf","excel","manual"]
    if sum(1 for t in quick_terms if t in text)>=2:
        return {"classification":"QUICK_AUTOMATION","status":"QUALIFIED","reason":"BOUNDED_REPETITIVE_WORKFLOW"}
    return {"classification":"BUSINESS_SYSTEM","status":"QUALIFIED","reason":"STRUCTURED_BUSINESS_WORKFLOW"}

def free_result(c:Dict, problem:str, outcome:str)->Dict:
    return {
      "problem_summary":problem.strip()[:500],
      "solution_direction":f"Explore a {c['classification'].replace('_',' ').title()} approach aligned to the desired outcome: {outcome.strip()[:280]}",
      "assessment_category":c["classification"],
      "recommended_next_step":"Scope review" if c["status"]=="QUALIFIED" else "Clarify requirements / human review",
      "binding_price":None,
      "binding_delivery_date":None,
      "architecture":None,
      "source_code":None
    }

def can_auto_quote()->bool:
    return False
