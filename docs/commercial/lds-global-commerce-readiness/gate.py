#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

REQUIRED = (
    "country_identity","currency","tax_treatment","contract_jurisdiction",
    "privacy_data_handling","data_residency","payment_method",
    "support_timezone","builder_capability","delivery_uat",
    "invoice_export_requirements","sanctions_restrictions_check"
)

@dataclass(frozen=True)
class CountryEvidence:
    country_code: str
    currency_supported: bool
    tax_known: bool
    contract_jurisdiction_known: bool
    privacy_known: bool
    data_residency_known: bool
    payment_supported: bool
    support_timezone_supported: bool
    builder_capability_supported: bool
    delivery_uat_supported: bool
    invoice_export_known: bool
    restrictions_cleared: bool
    evidence_current: bool
    human_approved: bool
    explicitly_prohibited: bool=False

def classify_country(e: CountryEvidence) -> Dict:
    if not e.country_code or len(e.country_code) != 2:
        return {"classification":"MANUAL_REVIEW","reason":"INVALID_OR_UNKNOWN_COUNTRY"}
    if e.explicitly_prohibited:
        return {"classification":"NOT_SUPPORTED","reason":"EXPLICITLY_PROHIBITED"}
    checks = {
        "currency": e.currency_supported,
        "tax_treatment": e.tax_known,
        "contract_jurisdiction": e.contract_jurisdiction_known,
        "privacy_data_handling": e.privacy_known,
        "data_residency": e.data_residency_known,
        "payment_method": e.payment_supported,
        "support_timezone": e.support_timezone_supported,
        "builder_capability": e.builder_capability_supported,
        "delivery_uat": e.delivery_uat_supported,
        "invoice_export_requirements": e.invoice_export_known,
        "sanctions_restrictions_check": e.restrictions_cleared,
        "evidence_current": e.evidence_current,
    }
    missing=[k for k,v in checks.items() if not v]
    if missing:
        return {"classification":"MANUAL_REVIEW","reason":"EVIDENCE_OR_CAPABILITY_GAP","missing":missing}
    if not e.human_approved:
        return {"classification":"MANUAL_REVIEW","reason":"HUMAN_APPROVAL_REQUIRED"}
    return {"classification":"SUPPORTED","reason":"ALL_GATES_PASS"}

def order_authority(classification:str, public_payment_ready:bool) -> Dict:
    if classification == "NOT_SUPPORTED":
        return {"decision":"REJECT_PAID_ORDER","enquiry_allowed":False}
    if classification != "SUPPORTED":
        return {"decision":"MANUAL_REVIEW_ONLY","enquiry_allowed":True}
    if not public_payment_ready:
        return {"decision":"QUOTE_ONLY_NO_AUTOMATIC_CHECKOUT","enquiry_allowed":True}
    return {"decision":"PAID_ORDER_ELIGIBLE","enquiry_allowed":True}

def global_status(country_results:Dict[str,str]) -> Dict:
    values=list(country_results.values())
    supported=sum(1 for v in values if v=="SUPPORTED")
    manual=sum(1 for v in values if v=="MANUAL_REVIEW")
    blocked=sum(1 for v in values if v=="NOT_SUPPORTED")
    return {
        "supported_count":supported,
        "manual_review_count":manual,
        "not_supported_count":blocked,
        "global_paid_order_ready": supported > 0 and manual == 0 and blocked == 0
    }
