#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

ALLOWED_CHANNELS={
    "GOOGLE_SEARCH","CLUTCH","UPWORK","SEO_CONTENT","LINKEDIN",
    "REFERRAL_PARTNERS","AFFILIATE_PARTNERS","PRODUCT_HUNT","EVIDENCE_APPROVED_LOCAL_CHANNELS"
}

@dataclass(frozen=True)
class LeadEvidence:
    source_channel: str
    valid_contact_method: bool
    lawful_contact_basis: bool
    source_attribution: bool
    intelligible_need: bool
    service_match: bool
    country_known: bool
    unresolved_fraud_or_abuse: bool=False
    explicitly_unsupported_market: bool=False
    prohibited_service: bool=False

def qualify_lead(e:LeadEvidence)->Dict:
    if e.source_channel not in ALLOWED_CHANNELS:
        return {"status":"HOLD","reason":"UNKNOWN_OR_UNAPPROVED_CHANNEL"}
    if e.unresolved_fraud_or_abuse:
        return {"status":"HOLD","reason":"FRAUD_OR_ABUSE_REVIEW_REQUIRED"}
    if e.explicitly_unsupported_market:
        return {"status":"HOLD","reason":"UNSUPPORTED_MARKET"}
    if e.prohibited_service:
        return {"status":"HOLD","reason":"PROHIBITED_SERVICE"}
    checks={
        "valid_contact_method":e.valid_contact_method,
        "lawful_contact_basis":e.lawful_contact_basis,
        "source_attribution":e.source_attribution,
        "intelligible_need":e.intelligible_need,
        "service_match":e.service_match,
        "country_known":e.country_known,
    }
    missing=[k for k,v in checks.items() if not v]
    if missing:
        return {"status":"NEEDS_QUALIFICATION","reason":"QUALIFICATION_GAP","missing":missing}
    return {
        "status":"QUALIFIED_LEAD",
        "reason":"ACQUISITION_GATES_PASS",
        "market_support_authority":False,
        "payment_authority":False,
        "next_stage":"MARKET_SUPPORT_CHECK"
    }

def commercial_handoff(qualified:bool, market_support_decision:str, commerce_dependency_ready:bool, lifecycle_dependency_ready:bool)->Dict:
    if not qualified:
        return {"status":"HOLD","reason":"QUALIFIED_LEAD_REQUIRED"}
    if not commerce_dependency_ready or not lifecycle_dependency_ready:
        return {"status":"CONDITIONAL_HOLD","reason":"DOWNSTREAM_DEPENDENCY_NOT_ON_MAIN"}
    if market_support_decision=="NOT_SUPPORTED":
        return {"status":"HOLD","reason":"MARKET_NOT_SUPPORTED"}
    if market_support_decision!="SUPPORTED":
        return {"status":"MANUAL_REVIEW","reason":"MARKET_SUPPORT_NOT_CONFIRMED"}
    return {
        "status":"READY_FOR_COMMERCIAL_HANDOFF",
        "reason":"DOWNSTREAM_GATES_AVAILABLE",
        "payment_authority":False,
        "production_authority":"HUMAN_ONLY"
    }
