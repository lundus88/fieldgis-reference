#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class SuccessEvidence:
    delivery_evidence: bool
    acceptance_evidence: bool
    satisfaction_confirmed: bool
    unresolved_issue: bool=False
    testimonial_permission: bool=False
    referral_permission: bool=False

def evaluate(e:SuccessEvidence)->Dict:
    if not e.delivery_evidence or not e.acceptance_evidence:
        return {"status":"SUCCESS_CHECK_PENDING","testimonial_allowed":False,"referral_allowed":False}
    if e.unresolved_issue:
        return {"status":"FOLLOW_UP_REQUIRED","testimonial_allowed":False,"referral_allowed":False}
    if not e.satisfaction_confirmed:
        return {"status":"SUCCESS_CHECK_PENDING","testimonial_allowed":False,"referral_allowed":False}
    return {
      "status":"SATISFACTION_CONFIRMED",
      "testimonial_allowed":bool(e.testimonial_permission),
      "referral_allowed":bool(e.referral_permission)
    }

def testimonial_action(e:SuccessEvidence)->Dict:
    r=evaluate(e)
    if not r.get("testimonial_allowed"):
        return {"decision":"HOLD","reason":"EXPLICIT_TESTIMONIAL_PERMISSION_REQUIRED"}
    return {"decision":"PREPARE_DRAFT_FOR_CUSTOMER_REVIEW","auto_publish":False}

def referral_action(e:SuccessEvidence)->Dict:
    r=evaluate(e)
    if not r.get("referral_allowed"):
        return {"decision":"HOLD","reason":"REFERRAL_PERMISSION_REQUIRED"}
    return {"decision":"REQUEST_INTRODUCTION","auto_contact_referral":False}
