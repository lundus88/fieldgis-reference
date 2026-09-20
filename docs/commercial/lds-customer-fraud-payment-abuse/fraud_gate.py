#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict,List

@dataclass(frozen=True)
class AbuseSignal:
    risk_id:str
    severity:str
    active:bool
    evidence_refs:tuple[str,...]=()

def evaluate(signals:List[AbuseSignal])->Dict:
    active=[s for s in signals if s.active]
    if not active:
        return {"classification":"CLEAR","actions":[]}
    for s in active:
        if s.severity not in {"P0","P1","P2","P3"}:
            raise ValueError("invalid severity")
        if not s.evidence_refs:
            return {"classification":"REVIEW","actions":["COLLECT_EVIDENCE"],"reason":"ACTIVE_SIGNAL_WITHOUT_EVIDENCE"}
    p0=any(s.severity=="P0" for s in active)
    return {
        "classification":"HIGH_RISK_REVIEW" if p0 else "REVIEW",
        "actions":sorted(set(
            (["HUMAN_SECURITY_ESCALATION","FREEZE_CONSEQUENTIAL_ACTIONS"] if p0 else ["HUMAN_REVIEW"])
            + ["PRESERVE_EVIDENCE"]
        ))
    }

def funding_gate(required:bool,funded:bool)->Dict:
    blocked=required and not funded
    return {"risk_id":"CFP-003","blocked":blocked,"action":"BLOCK_BUILD_START" if blocked else "ALLOW"}

def handover_gate(final_payment_required:bool,final_payment_received:bool)->Dict:
    blocked=final_payment_required and not final_payment_received
    return {"risk_id":"CFP-004","blocked":blocked,"action":"BLOCK_UNRESTRICTED_HANDOVER" if blocked else "ALLOW"}

def off_channel_payment_gate(approved_channel:bool,authoritative_order_exists:bool)->Dict:
    blocked=not approved_channel or not authoritative_order_exists
    return {"risk_id":"CFP-006","blocked":blocked,"action":"BLOCK_FINANCIAL_SIDE_EFFECT" if blocked else "ALLOW"}

def support_dispute_review(delivery_evidence:bool,usage_evidence:bool,customer_claim:str)->Dict:
    if not customer_claim:
        raise ValueError("claim required")
    conflicting=(delivery_evidence or usage_evidence) and customer_claim in {"NON_RECEIPT","NO_ACCESS","UNAUTHORIZED_AFTER_USE"}
    return {
        "classification":"REVIEW" if conflicting else "CLEAR",
        "potential_abuse":conflicting,
        "action":"HUMAN_DISPUTE_REVIEW" if conflicting else "NORMAL_SUPPORT"
    }

def security_request_gate(requests_secret:bool,requests_gate_bypass:bool,requests_unlogged_admin:bool)->Dict:
    active=any([requests_secret,requests_gate_bypass,requests_unlogged_admin])
    return {
        "risk_id":"CFP-007",
        "active":active,
        "severity":"P0" if active else "P3",
        "action":"DENY_AND_HUMAN_SECURITY_ESCALATE" if active else "ALLOW"
    }

def acceptance_reversal(accepted:bool,acceptance_evidence:bool,new_defect_evidence:bool)->Dict:
    review=accepted and acceptance_evidence and not new_defect_evidence
    return {
        "risk_id":"CFP-008",
        "review":review,
        "action":"HUMAN_REVIEW_KEEP_EVIDENCE" if review else "PROCESS_NEW_EVIDENCE"
    }

def dispute_evidence_pack(
    quote_ref:bool,sow_ref:bool,payment_ref:bool,artifact_ref:bool,
    delivery_ref:bool,acceptance_ref:bool,communications_ref:bool
)->Dict:
    fields={
      "quote":quote_ref,"sow":sow_ref,"payment":payment_ref,"artifact":artifact_ref,
      "delivery":delivery_ref,"acceptance":acceptance_ref,"communications":communications_ref
    }
    missing=sorted(k for k,v in fields.items() if not v)
    return {"complete":not missing,"missing":missing,"action":"READY_FOR_HUMAN_DISPUTE_REVIEW" if not missing else "COLLECT_EVIDENCE"}
