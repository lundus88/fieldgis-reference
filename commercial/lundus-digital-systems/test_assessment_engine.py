#!/usr/bin/env python3
import unittest
from assessment_engine import *

class AssessmentTests(unittest.TestCase):
    def test_high_risk_manual_review(self):
        a=Assessment("x","p","w","o",regulated_or_high_risk=True)
        self.assertEqual(classify(a)["status"],"MANUAL_REVIEW")
    def test_missing_context_needs_more_info(self):
        a=Assessment("x","","w","o")
        self.assertEqual(classify(a)["status"],"NEED_MORE_INFO")
    def test_geo_signal(self):
        a=Assessment("survey","map problem","field workflow","web gis",geo_signal=True)
        self.assertEqual(classify(a)["classification"],"GEO_AI_SOLUTION")
    def test_quick_automation(self):
        a=Assessment("services","manual quotation in Excel","Excel then PDF","faster quotation and follow-up")
        self.assertEqual(classify(a)["classification"],"QUICK_AUTOMATION")
    def test_free_result_has_no_binding_price(self):
        c={"classification":"BUSINESS_SYSTEM","status":"QUALIFIED"}
        r=free_result(c,"manual job tracking","central dashboard")
        self.assertIsNone(r["binding_price"])
        self.assertIsNone(r["architecture"])
    def test_auto_quote_disabled(self):
        self.assertFalse(can_auto_quote())

if __name__=="__main__":
    unittest.main()
