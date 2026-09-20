#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_tenant_mismatch_holds(self):
        r=assess(Usage(10,5,True,False,"v1"))
        self.assertEqual(r["status"],"HOLD")
    def test_cost_computed_for_internal_use(self):
        r=assess(Usage(10,5,True,True,"v1"))
        self.assertEqual(r["internal_cost_minor"],50)
        self.assertFalse(r["customer_charge_authorized"])
    def test_stale_evidence_reviews(self):
        r=assess(Usage(10,5,False,True,"v1"))
        self.assertIn("USAGE_EVIDENCE_STALE_OR_MISSING",r["risk_flags"])
    def test_cost_not_customer_price(self):
        self.assertFalse(internal_cost_is_customer_price())

if __name__=="__main__": unittest.main()
