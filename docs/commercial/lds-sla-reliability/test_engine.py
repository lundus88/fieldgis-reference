#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_policy_required(self):
        r=assess(IncidentEvidence("","SEV1",10,20,15,60,True,True))
        self.assertEqual(r["status"],"REVIEW")
    def test_breach_detected(self):
        r=assess(IncidentEvidence("v1","SEV1",20,80,15,60,True,True))
        self.assertEqual(r["response_status"],"BREACHED")
        self.assertEqual(r["resolution_status"],"BREACHED")
    def test_current_evidence_human_review(self):
        r=assess(IncidentEvidence("v1","SEV2",10,30,15,60,True,True))
        self.assertEqual(r["status"],"EVIDENCE_READY_FOR_HUMAN_REVIEW")
        self.assertFalse(r["service_credit_authorized"])
    def test_stale_monitoring_reviews(self):
        r=assess(IncidentEvidence("v1","SEV2",10,30,15,60,False,True))
        self.assertIn("MONITORING_EVIDENCE_STALE_OR_MISSING",r["risk_flags"])
    def test_no_auto_credit(self):
        self.assertFalse(automatic_service_credit_allowed())

if __name__=="__main__": unittest.main()
