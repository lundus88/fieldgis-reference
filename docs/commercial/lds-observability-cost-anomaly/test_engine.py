#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_cross_tenant_holds(self):
        r=assess(Metric(120,100,20,50,True,False,"v1"))
        self.assertEqual(r["status"],"HOLD")
    def test_warning_anomaly(self):
        r=assess(Metric(130,100,20,50,True,True,"v1"))
        self.assertEqual(r["status"],"WARNING_ANOMALY")
        self.assertFalse(r["root_cause_confirmed"])
    def test_critical_anomaly_no_auto_remediation(self):
        r=assess(Metric(170,100,20,50,True,True,"v1"))
        self.assertEqual(r["status"],"CRITICAL_ANOMALY")
        self.assertFalse(r["remediation_authorized"])
    def test_stale_evidence_reviews(self):
        r=assess(Metric(170,100,20,50,False,True,"v1"))
        self.assertEqual(r["status"],"REVIEW")
    def test_no_auto_shutdown(self):
        self.assertFalse(automatic_shutdown_allowed())

if __name__=="__main__": unittest.main()
