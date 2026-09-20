#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_missing_evidence_never_guessed(self):
        r=assess(ProcurementEvidence(False,False,"CERTIFICATION"))
        self.assertEqual(r["status"],"NEED_EVIDENCE")
    def test_customer_commitment_requires_review(self):
        r=assess(ProcurementEvidence(True,True,"POLICY",True,"v1"))
        self.assertIn("HUMAN_CONTRACT_REVIEW_REQUIRED",r["risk_flags"])
    def test_current_evidence_can_be_review_ready(self):
        r=assess(ProcurementEvidence(True,True,"SECURITY_CONTROL",False,"v1"))
        self.assertEqual(r["status"],"READY_FOR_HUMAN_PROCUREMENT_REVIEW")
        self.assertFalse(r["contractual_commitment_authorized"])
    def test_no_unsupported_claim(self):
        self.assertFalse(unsupported_claim_allowed())

if __name__=="__main__": unittest.main()
