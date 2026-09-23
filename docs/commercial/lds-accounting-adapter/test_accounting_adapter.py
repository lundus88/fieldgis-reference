import unittest
from adapter import ProviderCapabilities, CommercialEvidence, FakeAccountingProvider
from golden_transaction import run_golden

def evidence(**kw):
    d=dict(
        order_ref="O-1",customer_ref="C-1",approved_quote_ref="Q-1",
        amount=100.0,approved_quote_amount=100.0,payment_amount=100.0,
        currency="MYR",payment_reconciled=True,tax_einvoice_required=True
    )
    d.update(kw)
    return CommercialEvidence(**d)

class AccountingAdapterTests(unittest.TestCase):
    def full_provider(self):
        return FakeAccountingProvider(ProviderCapabilities(
            invoice_create=True,payment_record=True,einvoice_submit=True,
            einvoice_status=True,receipt_reference=True,reconciliation=True
        ))

    def test_golden_transaction_passes(self):
        self.assertEqual(run_golden()["status"],"PASS")

    def test_golden_transaction_without_einvoice_passes(self):
        self.assertEqual(run_golden(False)["status"],"PASS")

    def test_idempotent_invoice_replay(self):
        p=self.full_provider(); e=evidence()
        a=p.create_invoice("same",e); b=p.create_invoice("same",e)
        self.assertEqual(a["provider_invoice_ref"],b["provider_invoice_ref"])
        self.assertTrue(b["replay"])

    def test_idempotency_payload_collision_holds(self):
        p=self.full_provider()
        self.assertEqual(p.create_invoice("same",evidence())["status"],"PASS")
        self.assertEqual(
            p.create_invoice("same",evidence(customer_ref="C-2"))["reason"],
            "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
        )

    def test_missing_idempotency_holds(self):
        p=self.full_provider()
        self.assertEqual(p.create_invoice("",evidence())["reason"],"IDEMPOTENCY_KEY_REQUIRED")

    def test_invoice_quote_amount_mismatch_holds(self):
        p=self.full_provider()
        self.assertEqual(
            p.create_invoice("i",evidence(approved_quote_amount=99.0))["reason"],
            "INVOICE_QUOTATION_AMOUNT_MISMATCH"
        )

    def test_payment_amount_mismatch_holds(self):
        p=self.full_provider()
        self.assertEqual(
            p.record_payment("p",evidence(payment_amount=99.0))["reason"],
            "PAYMENT_AMOUNT_MISMATCH"
        )

    def test_unverified_invoice_capability_holds(self):
        p=FakeAccountingProvider(ProviderCapabilities())
        self.assertEqual(p.create_invoice("x",evidence())["status"],"HOLD")

    def test_unverified_einvoice_capability_holds(self):
        p=FakeAccountingProvider(ProviderCapabilities(invoice_create=True))
        inv=p.create_invoice("i",evidence())
        self.assertEqual(p.submit_einvoice("e",inv["provider_invoice_ref"])["status"],"HOLD")

    def test_payment_requires_authoritative_reconciliation(self):
        p=self.full_provider()
        self.assertEqual(
            p.record_payment("p",evidence(payment_reconciled=False))["reason"],
            "AUTHORITATIVE_PAYMENT_RECONCILIATION_REQUIRED"
        )

    def test_receipt_requires_paid_reconciliation(self):
        p=self.full_provider()
        self.assertEqual(
            p.create_receipt_reference("r",evidence(payment_reconciled=False))["reason"],
            "PAID_RECONCILIATION_REQUIRED"
        )

    def test_tax_einvoice_requires_validation(self):
        p=self.full_provider()
        e=evidence()
        inv=p.create_invoice("i",e)
        self.assertEqual(
            p.reconcile(e,inv["provider_invoice_ref"],"SUBMITTED")["reason"],
            "EINVOICE_VALIDATION_REQUIRED"
        )

    def test_non_tax_flow_can_reconcile(self):
        p=self.full_provider()
        e=evidence(tax_einvoice_required=False)
        inv=p.create_invoice("i",e)
        self.assertEqual(
            p.reconcile(e,inv["provider_invoice_ref"],"NOT_REQUIRED")["status"],
            "PASS"
        )

if __name__=="__main__":
    unittest.main()
