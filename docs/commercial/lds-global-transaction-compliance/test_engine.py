#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_unsupported_market_holds(self):
        r=assess(TransactionEvidence("XX","MY","USD",False))
        self.assertEqual(r["status"],"HOLD")
    def test_foreign_currency_requires_fx_evidence(self):
        r=assess(TransactionEvidence("SG","MY","SGD",True,tax_evidence_present=True,compliance_evidence_current=True))
        self.assertIn("FX_EVIDENCE_MISSING",r["risk_flags"])
    def test_complete_evidence_ready_for_human_review(self):
        r=assess(TransactionEvidence("SG","MY","SGD",True,3.2,"verified-provider",True,True,True))
        self.assertEqual(r["status"],"READY_FOR_HUMAN_REVIEW")
        self.assertFalse(r["customer_charge_authorized"])
    def test_never_invent_fx(self):
        self.assertFalse(invented_fx_allowed())

if __name__=="__main__": unittest.main()
