#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

VALID_TYPES={
 "GETTING_STARTED","HOW_TO","TROUBLESHOOTING","KNOWN_LIMITATION",
 "FAQ","SUPPORT_PATH","CHANGE_REQUEST_PATH","HANDOVER_REFERENCE"
}

@dataclass(frozen=True)
class Article:
    article_type:str
    version_matches:bool
    evidence_verified:bool
    evidence_current:bool
    customer_authorized:bool
    contains_security_bypass:bool=False
    contains_hidden_known_limit:bool=False
    requires_human_support:bool=False

def assess(a:Article)->Dict:
    if a.article_type not in VALID_TYPES:
        return {"status":"HOLD","reason":"UNKNOWN_ARTICLE_TYPE"}
    if not a.customer_authorized:
        return {"status":"DENY","reason":"CUSTOMER_NOT_AUTHORIZED"}
    if a.contains_security_bypass:
        return {"status":"HOLD","reason":"UNSAFE_SELF_SERVICE_GUIDANCE"}
    if a.contains_hidden_known_limit:
        return {"status":"HOLD","reason":"KNOWN_LIMITATION_MISREPRESENTED"}
    if not a.version_matches:
        return {"status":"REVIEW","reason":"VERSION_MISMATCH"}
    if not a.evidence_verified or not a.evidence_current:
        return {"status":"REVIEW","reason":"STALE_OR_UNVERIFIED_KNOWLEDGE"}
    return {
      "status":"CURRENT",
      "self_service_allowed":not a.requires_human_support,
      "support_route_required":bool(a.requires_human_support)
    }

def may_replace_security_escalation()->bool:
    return False
