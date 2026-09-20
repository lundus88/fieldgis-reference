#!/usr/bin/env python3
from dataclasses import dataclass, field
from typing import Dict, List, Set

MATERIAL_EFFECTS={
    "solution_type","scope","pricing_basis","delivery_effort",
    "dependency","compliance","acceptance_criteria","implementation_risk"
}

OFFER_MAP={
    "WEBSITE":"LD_LAUNCH",
    "ECOMMERCE":"LD_SYSTEM",
    "AI_AUTOMATION":"LD_AI",
    "AUTOMATION":"LD_AUTOMATE",
    "BUSINESS_SYSTEM":"LD_SYSTEM",
    "PORTAL":"LD_SYSTEM",
    "UNKNOWN":"LD_DISCOVERY",
}

@dataclass
class DiscoveryContext:
    objective: str=""
    solution_type: str="UNKNOWN"
    target_users: List[str]=field(default_factory=list)
    must_have: List[str]=field(default_factory=list)
    optional: List[str]=field(default_factory=list)
    exclusions: List[str]=field(default_factory=list)
    existing_assets: List[str]=field(default_factory=list)
    integrations: List[str]=field(default_factory=list)
    data_sensitivity: str="UNKNOWN"
    delivery_constraints: List[str]=field(default_factory=list)
    assumptions: List[str]=field(default_factory=list)
    unresolved_questions: List[str]=field(default_factory=list)
    acceptance_criteria_draft: List[str]=field(default_factory=list)
    contradictions: List[str]=field(default_factory=list)
    bypass_request: bool=False
    legal_or_regulatory_material: bool=False
    high_risk_data: bool=False
    integration_feasibility_unverified: bool=False

def should_ask(material_effects:Set[str], already_known:bool)->bool:
    if already_known:
        return False
    return bool(material_effects & MATERIAL_EFFECTS)

def recommend_offer(solution_type:str)->str:
    return OFFER_MAP.get(solution_type.upper(),"LD_DISCOVERY")

def next_question(ctx:DiscoveryContext)->Dict:
    if not ctx.objective.strip():
        return {"id":"objective","question":"What outcome do you want this project to achieve?","effects":["solution_type","scope"]}
    if ctx.solution_type=="UNKNOWN":
        return {"id":"solution_type","question":"Which best describes what you need: website, e-commerce, AI/automation, business system/portal, or something else?","effects":["solution_type","scope","pricing_basis"]}
    if not ctx.target_users:
        return {"id":"target_users","question":"Who will use this system or website?","effects":["scope","acceptance_criteria"]}
    if not ctx.must_have:
        return {"id":"must_have","question":"What must it be able to do for the project to be successful?","effects":["scope","pricing_basis","delivery_effort","acceptance_criteria"]}
    if not ctx.existing_assets:
        return {"id":"existing_assets","question":"Do you already have a domain, website, content, data, software, or other assets we should reuse?","effects":["dependency","delivery_effort","pricing_basis"]}
    if ctx.solution_type in {"AI_AUTOMATION","AUTOMATION","BUSINESS_SYSTEM","PORTAL","ECOMMERCE"} and not ctx.integrations:
        return {"id":"integrations","question":"Does this need to connect with any existing software, payment service, database, messaging service, or other system?","effects":["dependency","implementation_risk","pricing_basis"]}
    if ctx.data_sensitivity=="UNKNOWN":
        return {"id":"data_sensitivity","question":"Will the system handle public information only, or also customer, confidential, financial, health, identity, or other sensitive data?","effects":["compliance","implementation_risk","scope"]}
    if not ctx.delivery_constraints:
        return {"id":"delivery_constraints","question":"Are there any budget, launch-date, phased-delivery, or operational constraints we should design around?","effects":["scope","pricing_basis","delivery_effort"]}
    return {"id":None,"question":None,"effects":[]}

def evaluate(ctx:DiscoveryContext)->Dict:
    if ctx.bypass_request or ctx.legal_or_regulatory_material or ctx.high_risk_data:
        return {"status":"NEEDS_HUMAN_REVIEW","reason":"RISK_OR_COMPLIANCE_TRIGGER"}
    if ctx.contradictions:
        return {"status":"NEEDS_HUMAN_REVIEW","reason":"MATERIAL_REQUIREMENT_CONTRADICTION","items":ctx.contradictions}
    if ctx.integration_feasibility_unverified and ctx.integrations:
        return {"status":"NEEDS_HUMAN_REVIEW","reason":"MATERIAL_INTEGRATION_FEASIBILITY_UNVERIFIED"}
    q=next_question(ctx)
    if q["id"] is not None:
        return {"status":"DISCOVERY_IN_PROGRESS","next_question":q}
    return {
        "status":"READY_FOR_CUSTOMER_CONFIRMATION",
        "recommended_offer_family":recommend_offer(ctx.solution_type),
        "authoritative_quotation":False,
        "payment_authority":False,
        "production_authority":False
    }

def build_brief(ctx:DiscoveryContext)->Dict:
    return {
        "objective":ctx.objective,
        "solution_type":ctx.solution_type,
        "target_users":ctx.target_users,
        "must_have":ctx.must_have,
        "optional":ctx.optional,
        "exclusions":ctx.exclusions,
        "existing_assets":ctx.existing_assets,
        "integrations":ctx.integrations,
        "data_sensitivity":ctx.data_sensitivity,
        "delivery_constraints":ctx.delivery_constraints,
        "assumptions":ctx.assumptions,
        "unresolved_questions":ctx.unresolved_questions,
        "acceptance_criteria_draft":ctx.acceptance_criteria_draft,
        "confidence_state":evaluate(ctx)["status"],
        "customer_confirmation_state":"UNCONFIRMED",
        "recommended_offer_family":recommend_offer(ctx.solution_type),
        "authoritative_quotation":False
    }
