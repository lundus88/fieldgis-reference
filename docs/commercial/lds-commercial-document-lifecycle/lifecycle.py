#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

DOCUMENT_STATES={"DRAFT","ISSUED","VOID"}
PAYMENT_STATES={"UNPAID","PENDING_RECONCILIATION","PAID","REFUNDED","PARTIALLY_REFUNDED"}
MILESTONE_STATES={"NOT_FUNDED","FUNDED","BUILDING","DELIVERED","ACCEPTED"}

@dataclass(frozen=True)
class OrderEvidence:
    quote_approved: bool
    invoice_issued: bool
    provider_payment_verified: bool
    amount_reconciled: bool
    receipt_issued: bool
    milestone_funding_required: bool
    human_build_approval: bool

def issue_invoice(quote_approved:bool, amount_matches_quote:bool)->Dict:
    if not quote_approved:
        return {"decision":"HOLD","reason":"APPROVED_QUOTE_REQUIRED"}
    if not amount_matches_quote:
        return {"decision":"HOLD","reason":"AMOUNT_RECONCILIATION_FAILED"}
    return {"decision":"ISSUE_CANDIDATE","document_state":"ISSUED","payment_state":"UNPAID"}

def reconcile_payment(provider_verified:bool, amount_match:bool, order_match:bool)->Dict:
    if not provider_verified:
        return {"decision":"HOLD","payment_state":"PENDING_RECONCILIATION","reason":"PROVIDER_EVIDENCE_REQUIRED"}
    if not amount_match or not order_match:
        return {"decision":"HOLD","payment_state":"PENDING_RECONCILIATION","reason":"PAYMENT_MISMATCH"}
    return {"decision":"RECONCILED","payment_state":"PAID"}

def issue_receipt(payment_state:str, provider_ref_present:bool)->Dict:
    if payment_state!="PAID" or not provider_ref_present:
        return {"decision":"HOLD","reason":"VERIFIED_PAID_ORDER_REQUIRED"}
    return {"decision":"ISSUE_CANDIDATE","document_state":"ISSUED"}

def milestone_activation(e:OrderEvidence)->Dict:
    if e.milestone_funding_required and not (e.provider_payment_verified and e.amount_reconciled and e.receipt_issued):
        return {"decision":"HOLD","milestone_state":"NOT_FUNDED","reason":"FUNDED_MILESTONE_EVIDENCE_REQUIRED"}
    if not e.human_build_approval:
        return {"decision":"HUMAN_REVIEW","milestone_state":"FUNDED","reason":"BUILD_APPROVAL_REQUIRED"}
    return {"decision":"ALLOW_BUILD","milestone_state":"BUILDING"}

def notification_event(event:str,state:Dict)->Dict:
    allowed={"INVOICE_ISSUED","PAYMENT_CONFIRMED","RECEIPT_ISSUED","MILESTONE_FUNDED"}
    if event not in allowed:
        return {"decision":"HOLD","reason":"UNKNOWN_NOTIFICATION_EVENT"}
    requirements={
      "INVOICE_ISSUED": state.get("invoice_issued") is True,
      "PAYMENT_CONFIRMED": state.get("payment_state")=="PAID",
      "RECEIPT_ISSUED": state.get("receipt_issued") is True and state.get("payment_state")=="PAID",
      "MILESTONE_FUNDED": state.get("milestone_state") in {"FUNDED","BUILDING"}
    }
    return {"decision":"QUEUE_NOTIFICATION" if requirements[event] else "HOLD","event":event}

def void_document(current_state:str, reason_present:bool)->Dict:
    if current_state!="ISSUED" or not reason_present:
        return {"decision":"HOLD","reason":"ISSUED_DOCUMENT_AND_REASON_REQUIRED"}
    return {"decision":"VOID","preserve_original_reference":True,"audit_required":True}
