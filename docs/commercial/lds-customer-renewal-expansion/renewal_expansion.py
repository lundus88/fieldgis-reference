#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class CustomerGrowthEvidence:
    support_plan_expiring: bool
    satisfaction_confirmed: bool
    unresolved_issue: bool
    adoption_positive: bool
    new_workflow_need: bool
    profitability_healthy: bool
    capacity_available: bool
    customer_requested_change: bool=False

def evaluate(e:CustomerGrowthEvidence)->Dict:
    if e.unresolved_issue:
        return {
          "decision":"RETENTION_FOLLOW_UP",
          "reason":"UNRESOLVED_CUSTOMER_ISSUE",
          "auto_contact":False,
          "upsell_allowed":False
        }

    if e.support_plan_expiring:
        if not e.satisfaction_confirmed:
            return {
              "decision":"RENEWAL_REVIEW",
              "reason":"EXPIRY_WITHOUT_CONFIRMED_SATISFACTION",
              "auto_renew":False,
              "auto_contact":False
            }
        return {
          "decision":"RENEWAL_REVIEW",
          "reason":"SUPPORT_PLAN_EXPIRY",
          "auto_renew":False,
          "auto_contact":False
        }

    expansion_signal=e.new_workflow_need or e.customer_requested_change
    if expansion_signal:
        if not e.satisfaction_confirmed or not e.adoption_positive:
            return {
              "decision":"RETENTION_FOLLOW_UP",
              "reason":"EXPANSION_SIGNAL_WITHOUT_SUCCESS_EVIDENCE",
              "auto_contact":False,
              "upsell_allowed":False
            }
        if not e.profitability_healthy or not e.capacity_available:
            return {
              "decision":"EXPANSION_REVIEW",
              "reason":"COMMERCIAL_OR_CAPACITY_REVIEW_REQUIRED",
              "auto_contact":False,
              "binding_offer_allowed":False
            }
        return {
          "decision":"EXPANSION_REVIEW",
          "reason":"CUSTOMER_SUCCESS_AND_EXPANSION_SIGNAL",
          "auto_contact":False,
          "binding_offer_allowed":False
        }

    return {"decision":"NO_ACTION","reason":"NO_CURRENT_RENEWAL_OR_EXPANSION_SIGNAL"}

def can_auto_renew()->bool:
    return False

def can_auto_contact()->bool:
    return False
