#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Tuple, Dict

@dataclass(frozen=True)
class Subscription:
    org_id:str
    approved_plan:bool
    state:str
    entitlements:Tuple[str,...]
    payment_current:bool

def resolve(s:Subscription)->Dict:
    if not s.approved_plan:
        return {"status":"REVIEW","reason":"APPROVED_PLAN_REQUIRED","entitlements":[]}
    if s.state not in {"TRIAL","ACTIVE","PAST_DUE","CANCEL_PENDING","CANCELLED"}:
        return {"status":"REVIEW","reason":"INVALID_SUBSCRIPTION_STATE","entitlements":[]}
    if s.state=="CANCELLED":
        return {"status":"INACTIVE","entitlements":[],"irreversible_action_authorized":False}
    renewal="CURRENT" if s.payment_current else "PAYMENT_REVIEW"
    return {"status":"ENTITLEMENT_RESOLVED","entitlements":list(s.entitlements),"renewal_state":renewal,"auto_charge":False,"irreversible_action_authorized":False}

def auto_charge_allowed()->bool:
    return False
