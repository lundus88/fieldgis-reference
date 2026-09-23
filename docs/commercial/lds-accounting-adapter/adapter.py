#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict
import hashlib
import json

@dataclass(frozen=True)
class ProviderCapabilities:
    invoice_create: bool = False
    payment_record: bool = False
    einvoice_submit: bool = False
    einvoice_status: bool = False
    receipt_reference: bool = False
    reconciliation: bool = False

@dataclass(frozen=True)
class CommercialEvidence:
    order_ref: str
    customer_ref: str
    approved_quote_ref: str
    amount: float
    approved_quote_amount: float
    payment_amount: float
    currency: str
    payment_reconciled: bool
    tax_einvoice_required: bool

def _digest(payload: Dict) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()

class FakeAccountingProvider:
    """Deterministic non-Production provider used only for contract tests."""
    def __init__(self, capabilities: ProviderCapabilities):
        self.capabilities=capabilities
        self._seen={}
        self._invoice_status={}

    def _mutate(self, op:str, idem:str, payload:Dict)->Dict:
        if not idem:
            return {"status":"HOLD","reason":"IDEMPOTENCY_KEY_REQUIRED"}
        key=(op,idem)
        payload_digest=_digest(payload)
        if key in self._seen:
            previous=self._seen[key]
            if previous["request_digest"] != payload_digest:
                return {"status":"HOLD","reason":"IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"}
            return dict(previous, replay=True)
        result={
            "status":"PASS",
            "operation":op,
            "request_digest":payload_digest,
            "evidence_digest":_digest({"op":op,"idem":idem,"payload":payload}),
            "replay":False
        }
        self._seen[key]=result
        return result

    def create_invoice(self, idem:str, evidence:CommercialEvidence)->Dict:
        if not self.capabilities.invoice_create:
            return {"status":"HOLD","reason":"PROVIDER_INVOICE_CAPABILITY_UNVERIFIED"}
        if not evidence.approved_quote_ref or evidence.amount <= 0 or not evidence.order_ref or not evidence.customer_ref:
            return {"status":"HOLD","reason":"INVOICE_EVIDENCE_INCOMPLETE"}
        if evidence.amount != evidence.approved_quote_amount:
            return {"status":"HOLD","reason":"INVOICE_QUOTATION_AMOUNT_MISMATCH"}
        r=self._mutate("create_invoice",idem,evidence.__dict__)
        if r["status"]=="PASS":
            inv="INV-"+r["evidence_digest"][:12].upper()
            r["provider_invoice_ref"]=inv
            self._invoice_status[inv]="CREATED"
        return r

    def submit_einvoice(self, idem:str, provider_invoice_ref:str)->Dict:
        if not self.capabilities.einvoice_submit:
            return {"status":"HOLD","reason":"PROVIDER_EINVOICE_SUBMIT_CAPABILITY_UNVERIFIED"}
        if provider_invoice_ref not in self._invoice_status:
            return {"status":"HOLD","reason":"UNKNOWN_PROVIDER_INVOICE"}
        r=self._mutate("submit_einvoice",idem,{"provider_invoice_ref":provider_invoice_ref})
        if r["status"]=="PASS":
            self._invoice_status[provider_invoice_ref]="VALIDATED"
            r["compliance_status"]="VALIDATED"
            r["compliance_reference"]="EINV-"+r["evidence_digest"][:12].upper()
        return r

    def record_payment(self, idem:str, evidence:CommercialEvidence)->Dict:
        if not self.capabilities.payment_record:
            return {"status":"HOLD","reason":"PROVIDER_PAYMENT_CAPABILITY_UNVERIFIED"}
        if not evidence.payment_reconciled:
            return {"status":"HOLD","reason":"AUTHORITATIVE_PAYMENT_RECONCILIATION_REQUIRED"}
        if evidence.payment_amount != evidence.amount:
            return {"status":"HOLD","reason":"PAYMENT_AMOUNT_MISMATCH"}
        return self._mutate("record_payment",idem,evidence.__dict__)

    def create_receipt_reference(self, idem:str, evidence:CommercialEvidence)->Dict:
        if not self.capabilities.receipt_reference:
            return {"status":"HOLD","reason":"PROVIDER_RECEIPT_CAPABILITY_UNVERIFIED"}
        if not evidence.payment_reconciled:
            return {"status":"HOLD","reason":"PAID_RECONCILIATION_REQUIRED"}
        if evidence.payment_amount != evidence.amount:
            return {"status":"HOLD","reason":"RECEIPT_PAYMENT_AMOUNT_MISMATCH"}
        r=self._mutate("create_receipt_reference",idem,evidence.__dict__)
        if r["status"]=="PASS":
            r["receipt_reference"]="RCT-"+r["evidence_digest"][:12].upper()
        return r

    def reconcile(self, evidence:CommercialEvidence, invoice_ref:str, compliance_status:str)->Dict:
        if not self.capabilities.reconciliation:
            return {"status":"HOLD","reason":"PROVIDER_RECONCILIATION_CAPABILITY_UNVERIFIED"}
        if not evidence.payment_reconciled:
            return {"status":"HOLD","reason":"PAYMENT_NOT_RECONCILED"}
        if evidence.amount != evidence.approved_quote_amount:
            return {"status":"HOLD","reason":"QUOTE_INVOICE_RECONCILIATION_FAILED"}
        if evidence.payment_amount != evidence.amount:
            return {"status":"HOLD","reason":"PAYMENT_INVOICE_RECONCILIATION_FAILED"}
        if evidence.tax_einvoice_required and compliance_status!="VALIDATED":
            return {"status":"HOLD","reason":"EINVOICE_VALIDATION_REQUIRED"}
        if not invoice_ref:
            return {"status":"HOLD","reason":"ACCOUNTING_INVOICE_REFERENCE_REQUIRED"}
        return {
            "status":"PASS",
            "reason":"ACCOUNTING_RECONCILED",
            "evidence_digest":_digest({
                "order":evidence.order_ref,
                "invoice":invoice_ref,
                "compliance":compliance_status,
                "amount":evidence.amount,
                "currency":evidence.currency
            })
        }
