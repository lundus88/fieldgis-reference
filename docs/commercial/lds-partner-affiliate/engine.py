#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Tuple, Dict

@dataclass(frozen=True)
class PartnerSale:
    partner_id:str
    customer_id:str
    partner_status:str
    sale_status:str
    gross_amount_minor:int
    commission_rate_bps:int
    policy_version:str
    self_referral:bool=False
    duplicate_attribution:bool=False
    suspicious_loop:bool=False
    refunded_or_disputed:bool=False

def assess(s:PartnerSale)->Dict:
    flags=[]
    if s.partner_status!="APPROVED":
        return {"status":"REVIEW","risk_flags":["PARTNER_NOT_APPROVED"],"commission_eligible_minor":0,"payout_authorized":False}
    if not s.policy_version or s.commission_rate_bps < 0 or s.commission_rate_bps > 10000:
        return {"status":"REVIEW","risk_flags":["INVALID_COMMISSION_POLICY"],"commission_eligible_minor":0,"payout_authorized":False}
    if s.self_referral: flags.append("SELF_REFERRAL")
    if s.duplicate_attribution: flags.append("DUPLICATE_ATTRIBUTION")
    if s.suspicious_loop: flags.append("SUSPICIOUS_ATTRIBUTION_LOOP")
    if s.refunded_or_disputed: flags.append("REFUND_OR_DISPUTE")
    if s.sale_status!="PAID_RECONCILED": flags.append("SALE_NOT_RECONCILED")
    eligible=0
    if not flags:
        eligible=round(s.gross_amount_minor*s.commission_rate_bps/10000)
    return {
      "status":"ELIGIBLE_FOR_HUMAN_PAYOUT_REVIEW" if eligible>0 else "REVIEW",
      "risk_flags":flags,
      "commission_eligible_minor":eligible,
      "payout_authorized":False
    }

def automatic_payout_allowed()->bool:
    return False
