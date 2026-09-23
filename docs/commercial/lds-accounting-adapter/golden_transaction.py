#!/usr/bin/env python3
from adapter import ProviderCapabilities, CommercialEvidence, FakeAccountingProvider

def run_golden(require_einvoice:bool=True):
    caps=ProviderCapabilities(
        invoice_create=True,
        payment_record=True,
        einvoice_submit=True,
        einvoice_status=True,
        receipt_reference=True,
        reconciliation=True,
    )
    provider=FakeAccountingProvider(caps)
    e=CommercialEvidence(
        order_ref="LD-GOLDEN-001",
        customer_ref="CUST-GOLDEN-001",
        approved_quote_ref="Q-LD-GOLDEN-001",
        amount=497.00,
        approved_quote_amount=497.00,
        payment_amount=497.00,
        currency="MYR",
        payment_reconciled=True,
        tax_einvoice_required=require_einvoice,
    )

    invoice=provider.create_invoice("golden:invoice:001",e)
    assert invoice["status"]=="PASS"
    invoice_replay=provider.create_invoice("golden:invoice:001",e)
    assert invoice_replay["status"]=="PASS" and invoice_replay["replay"] is True

    payment=provider.record_payment("golden:payment:001",e)
    assert payment["status"]=="PASS"

    compliance_status="NOT_REQUIRED"
    einvoice=None
    if require_einvoice:
        einvoice=provider.submit_einvoice("golden:einvoice:001",invoice["provider_invoice_ref"])
        assert einvoice["status"]=="PASS"
        compliance_status=einvoice["compliance_status"]

    receipt=provider.create_receipt_reference("golden:receipt:001",e)
    assert receipt["status"]=="PASS"

    reconciliation=provider.reconcile(e,invoice["provider_invoice_ref"],compliance_status)
    assert reconciliation["status"]=="PASS"

    return {
        "status":"PASS",
        "order_ref":e.order_ref,
        "invoice_ref":invoice["provider_invoice_ref"],
        "einvoice":einvoice,
        "receipt_reference":receipt["receipt_reference"],
        "reconciliation":reconciliation,
        "production_authority":False
    }

if __name__=="__main__":
    print(run_golden())
