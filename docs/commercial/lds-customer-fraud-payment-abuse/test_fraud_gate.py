#!/usr/bin/env python3
import unittest
from fraud_gate import *

class FraudGateTests(unittest.TestCase):
    def test_no_signal_clear(self):
        self.assertEqual(evaluate([])["classification"],"CLEAR")

    def test_signal_without_evidence_requires_collection(self):
        r=evaluate([AbuseSignal("CFP-001","P1",True,())])
        self.assertEqual(r["reason"],"ACTIVE_SIGNAL_WITHOUT_EVIDENCE")

    def test_p0_freezes_consequential_actions(self):
        r=evaluate([AbuseSignal("CFP-007","P0",True,("ticket-1",))])
        self.assertIn("FREEZE_CONSEQUENTIAL_ACTIONS",r["actions"])

    def test_unfunded_milestone_blocks_build(self):
        self.assertEqual(funding_gate(True,False)["action"],"BLOCK_BUILD_START")

    def test_final_payment_blocks_unrestricted_handover(self):
        self.assertEqual(handover_gate(True,False)["action"],"BLOCK_UNRESTRICTED_HANDOVER")

    def test_off_channel_payment_blocks_side_effect(self):
        self.assertEqual(off_channel_payment_gate(False,True)["action"],"BLOCK_FINANCIAL_SIDE_EFFECT")

    def test_nonreceipt_conflicting_with_delivery_evidence_requires_review(self):
        r=support_dispute_review(True,False,"NON_RECEIPT")
        self.assertTrue(r["potential_abuse"])
        self.assertEqual(r["action"],"HUMAN_DISPUTE_REVIEW")

    def test_secret_request_is_p0(self):
        self.assertEqual(security_request_gate(True,False,False)["severity"],"P0")

    def test_acceptance_reversal_preserves_evidence(self):
        r=acceptance_reversal(True,True,False)
        self.assertTrue(r["review"])

    def test_evidence_pack_requires_all_core_refs(self):
        r=dispute_evidence_pack(True,True,True,True,True,False,True)
        self.assertFalse(r["complete"])
        self.assertIn("acceptance",r["missing"])

if __name__=="__main__":
    unittest.main()
