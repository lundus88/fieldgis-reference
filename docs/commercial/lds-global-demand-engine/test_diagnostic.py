#!/usr/bin/env python3
import unittest
from diagnostic import DiagnosticEvidence,assess

class DiagnosticTests(unittest.TestCase):
    def test_no_reported_friction_scores_100(self):
        e=DiagnosticEvidence(False,False,False,False,False,False,False,False)
        r=assess(e)
        self.assertEqual(r["digital_efficiency_score"],100)
        self.assertTrue(r["advisory_only"])
        self.assertFalse(r["commercial_authority"])

    def test_multiple_frictions_reduce_score_and_create_priorities(self):
        e=DiagnosticEvidence(True,True,True,True,True,True,True,True)
        r=assess(e)
        self.assertEqual(r["digital_efficiency_score"],0)
        self.assertEqual(len(r["priority_opportunity_areas"]),3)
        self.assertFalse(r["roi_guarantee"])

    def test_recommendations_are_problem_led(self):
        e=DiagnosticEvidence(False,False,True,False,False,False,False,True)
        r=assess(e)
        self.assertIn("customer_data_fragmented",r["priority_opportunity_areas"])
        self.assertGreaterEqual(len(r["recommended_next_actions"]),1)

if __name__=="__main__":
    unittest.main()
