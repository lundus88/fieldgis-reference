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


@dataclass(frozen=True)
class InternationalOperatingEvidence:
    home_country_code: str
    locale_language_ready: bool
    multi_currency_ready: bool
    timezone_normalization_ready: bool
    jurisdiction_knowledge_ready: bool
    cross_border_payment_ready: bool
    accounting_invoice_ready: bool
    privacy_security_ready: bool
    support_delivery_ready: bool
    observability_recovery_ready: bool
    evidence_current: bool
    real_cross_border_paid_transaction_verified: bool
    delivery_acceptance_verified: bool
    accounting_receipt_verified: bool
    transaction_country_code: str | None = None
    human_validated_international_claim: bool = False


def assess_international_readiness(
    country_results: Dict[str, str],
    evidence: InternationalOperatingEvidence,
) -> Dict:
    home = str(evidence.home_country_code or "").upper()
    if len(home) != 2:
        return {
            "status": "HOLD",
            "reason": "HOME_COUNTRY_REQUIRED",
            "public_international_claim_allowed": False,
            "worldwide_claim_allowed": False,
            "production_authority": "HUMAN_ONLY",
        }

    normalized = {str(k).upper(): str(v) for k, v in country_results.items()}
    supported_foreign = sorted(
        code for code, state in normalized.items()
        if code != home and state == "SUPPORTED"
    )

    if not supported_foreign:
        return {
            "status": "HOLD",
            "reason": "NO_FOREIGN_MARKET_SUPPORTED",
            "supported_foreign_markets": [],
            "public_international_claim_allowed": False,
            "worldwide_claim_allowed": False,
            "production_authority": "HUMAN_ONLY",
        }

    operational_checks = {
        "locale_language": evidence.locale_language_ready,
        "multi_currency": evidence.multi_currency_ready,
        "timezone_normalization": evidence.timezone_normalization_ready,
        "jurisdiction_knowledge": evidence.jurisdiction_knowledge_ready,
        "cross_border_payment": evidence.cross_border_payment_ready,
        "accounting_invoice": evidence.accounting_invoice_ready,
        "privacy_security": evidence.privacy_security_ready,
        "support_delivery": evidence.support_delivery_ready,
        "observability_recovery": evidence.observability_recovery_ready,
        "evidence_current": evidence.evidence_current,
    }
    missing = sorted(k for k, v in operational_checks.items() if not v)
    if missing:
        return {
            "status": "HOLD",
            "reason": "INTERNATIONAL_OPERATING_GAP",
            "missing": missing,
            "supported_foreign_markets": supported_foreign,
            "public_international_claim_allowed": False,
            "worldwide_claim_allowed": False,
            "production_authority": "HUMAN_ONLY",
        }

    transaction_country = str(evidence.transaction_country_code or "").upper()
    transaction_bound = (
        evidence.real_cross_border_paid_transaction_verified
        and evidence.delivery_acceptance_verified
        and evidence.accounting_receipt_verified
        and transaction_country in supported_foreign
    )

    if not transaction_bound:
        return {
            "status": "INTERNATIONAL_CANDIDATE",
            "reason": "OPERATING_EVIDENCE_COMPLETE_REAL_CROSS_BORDER_PROOF_REQUIRED",
            "supported_foreign_markets": supported_foreign,
            "public_international_claim_allowed": False,
            "worldwide_claim_allowed": False,
            "production_authority": "HUMAN_ONLY",
            "claim_discipline": "CANDIDATE_NOT_VALIDATED",
        }

    if not evidence.human_validated_international_claim:
        return {
            "status": "HUMAN_GATE",
            "reason": "HUMAN_VALIDATION_REQUIRED_FOR_INTERNATIONAL_CLAIM",
            "supported_foreign_markets": supported_foreign,
            "validated_transaction_country": transaction_country,
            "public_international_claim_allowed": False,
            "worldwide_claim_allowed": False,
            "production_authority": "HUMAN_ONLY",
        }

    return {
        "status": "INTERNATIONAL_VALIDATED",
        "reason": "REAL_CROSS_BORDER_END_TO_END_PROOF_VERIFIED",
        "supported_foreign_markets": supported_foreign,
        "validated_transaction_country": transaction_country,
        "public_international_claim_allowed": True,
        "worldwide_claim_allowed": False,
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "self_approval": "FORBIDDEN",
        "authority_widening": "DISABLED",
    }
