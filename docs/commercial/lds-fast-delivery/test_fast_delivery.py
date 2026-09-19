#!/usr/bin/env python3
import unittest
from fast_delivery import Intake, classify_project, plan_intake, uat_transition

class FastDeliveryTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(classify_project(2), "QUICK_AUTOMATION")
        self.assertEqual(classify_project(6), "STARTER_SYSTEM")
        self.assertEqual(classify_project(15), "SEMI_CUSTOM")
        self.assertEqual(classify_project(25), "COMPLEX")

    def test_unbounded_scope_never_enters_build(self):
        r = plan_intake(Intake(True, False, True, 3), 0, 10)
        self.assertEqual(r["state"], "CLIENT_ACTION_REQUIRED")

    def test_capacity_exhaustion_schedules(self):
        r = plan_intake(Intake(True, True, True, 5), 8, 10)
        self.assertEqual(r["state"], "SCHEDULED")
        self.assertEqual(r["reason"], "CAPACITY_EXHAUSTED")

    def test_fast_track_does_not_bypass_capacity(self):
        r = plan_intake(Intake(True, True, True, 4, lane="FAST_TRACK"), 8, 10)
        self.assertEqual(r["state"], "SCHEDULED")
        self.assertEqual(r["reason"], "FAST_TRACK_CAPACITY_NOT_RESERVED")

    def test_ready_build_has_human_final_acceptance(self):
        r = plan_intake(Intake(True, True, True, 3), 0, 10)
        self.assertEqual(r["state"], "BUILDING")
        self.assertEqual(r["final_acceptance_authority"], "HUMAN_ONLY")

    def test_uat_rejected_routes_back_to_build(self):
        r = uat_transition("REJECTED")
        self.assertEqual(r["state"], "BUILDING")

    def test_high_issue_blocks_delivery(self):
        r = uat_transition("ACCEPTED_WITH_MINOR_ISSUES", "HIGH")
        self.assertEqual(r["state"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
