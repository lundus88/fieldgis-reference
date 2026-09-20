#!/usr/bin/env python3
import unittest
from pricing_estimation import *

class PricingTests(unittest.TestCase):
    def test_scope_required(self):
        e=PricingEvidence(False,100000,comparable_project_count=10)
        self.assertEqual(estimate(e)["status"],"INSUFFICIENT_EVIDENCE")
    def test_stale_cost_reviews(self):
        e=PricingEvidence(True,100000,comparable_project_count=10,inputs_current=False)
        self.assertEqual(estimate(e)["status"],"REVIEW")
    def test_low_sample_not_high_confidence(self):
        e=PricingEvidence(True,100000,comparable_project_count=1)
        r=estimate(e)
        self.assertEqual(r["evidence_confidence"],"LOW")
        self.assertEqual(r["status"],"INSUFFICIENT_EVIDENCE")
    def test_medium_sample_ready_for_human_review(self):
        e=PricingEvidence(True,100000,comparable_project_count=4)
        self.assertEqual(estimate(e)["status"],"READY_FOR_HUMAN_PRICING_REVIEW")
    def test_never_authorizes_customer_price(self):
        e=PricingEvidence(True,100000,comparable_project_count=10)
        r=estimate(e)
        self.assertFalse(r["customer_price_authorized"])
        self.assertFalse(r["auto_quote"])
        self.assertFalse(r["auto_publish"])
    def test_factory_credit_not_customer_price(self):
        self.assertFalse(factory_credit_to_customer_price_allowed())

if __name__=="__main__": unittest.main()
