#!/usr/bin/env python3
import unittest
from lifecycle import *

class LifecycleTests(unittest.TestCase):
    def test_invoice_requires_approved_quote(self):
        self.assertEqual(issue_invoice(False,True)["decision"],"HOLD")
    def test_invoice_amount_must_match_quote(self):
        self.assertEqual(issue_invoice(True,False)["reason"],"AMOUNT_RECONCILIATION_FAILED")
    def test_payment_never_paid_without_provider_evidence(self):
        self.assertEqual(reconcile_payment(False,True,True)["payment_state"],"PENDING_RECONCILIATION")
    def test_payment_mismatch_holds(self):
        self.assertEqual(reconcile_payment(True,False,True)["decision"],"HOLD")
    def test_receipt_requires_verified_paid_order(self):
        self.assertEqual(issue_receipt("UNPAID",True)["decision"],"HOLD")
    def test_funded_milestone_requires_receipt_when_required(self):
        e=OrderEvidence(True,True,True,True,False,True,True)
        self.assertEqual(milestone_activation(e)["milestone_state"],"NOT_FUNDED")
    def test_human_build_gate_remains(self):
        e=OrderEvidence(True,True,True,True,True,True,False)
        self.assertEqual(milestone_activation(e)["decision"],"HUMAN_REVIEW")
    def test_invoice_notification_requires_issued_state(self):
        self.assertEqual(notification_event("INVOICE_ISSUED",{"invoice_issued":False})["decision"],"HOLD")
    def test_receipt_notification_requires_paid_and_issued(self):
        self.assertEqual(notification_event("RECEIPT_ISSUED",{"receipt_issued":True,"payment_state":"UNPAID"})["decision"],"HOLD")
    def test_void_preserves_original_reference(self):
        r=void_document("ISSUED",True)
        self.assertTrue(r["preserve_original_reference"])

if __name__=="__main__":
    unittest.main()
