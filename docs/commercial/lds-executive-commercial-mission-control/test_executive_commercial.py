#!/usr/bin/env python3
import unittest
from executive_commercial import *

def m(v=1,source_status="AUTHORITATIVE",freshness="CURRENT",completeness_pct=100,contradictory=False):
    return MetricEvidence(v,source_status,freshness,completeness_pct,contradictory)

class ExecutiveCommercialTests(unittest.TestCase):
    def test_stale_revenue_not_confirmed(self):
        self.assertEqual(normalize("revenue",m(freshness="STALE"))["status"],"REVIEW")
    def test_incomplete_margin_not_confirmed(self):
        self.assertEqual(normalize("margin",m(completeness_pct=60))["status"],"REVIEW")
    def test_contradiction_holds(self):
        self.assertEqual(normalize("pipeline",m(contradictory=True))["status"],"HOLD")
    def test_non_authoritative_source_reviews(self):
        self.assertEqual(normalize("capacity",m(source_status="INFERRED"))["status"],"REVIEW")
    def test_missing_metric_reviews_overall(self):
        r=executive_view({"pipeline":m()})
        self.assertEqual(r["overall"],"HUMAN_REVIEW")
    def test_exception_routes_human_review(self):
        metrics={k:m() for k in ["pipeline","revenue","margin","capacity","customer_health","recurring_revenue"]}
        self.assertEqual(executive_view(metrics,exceptions=1)["overall"],"HUMAN_REVIEW")
    def test_dashboard_has_no_execution_authority(self):
        self.assertFalse(can_execute_commercial_action())

if __name__=="__main__":
    unittest.main()
