#!/usr/bin/env python3
import unittest
from engine import *

class AutonomousOperationsTests(unittest.TestCase):
    def test_standard_launch_can_auto_kickoff(self):
        r=auto_kickoff(AutoKickoffEvidence(True,True,"LD_LAUNCH",True,"PASS"))
        self.assertTrue(r["eligible"])
        self.assertEqual(r["reason"],"AUTONOMOUS_KICKOFF_ELIGIBLE")
        self.assertFalse(r["production_authority"])

    def test_unknown_capability_human_gate(self):
        r=auto_kickoff(AutoKickoffEvidence(True,True,"UNKNOWN",True,"PASS"))
        self.assertFalse(r["eligible"])
        self.assertEqual(r["status"],"HUMAN_GATE")

    def test_capacity_overload_queues_without_fake_capacity(self):
        r=capacity_decision(CapacitySnapshot(active_jobs=10,max_concurrent_jobs=10))
        self.assertEqual(r["status"],"AUTO_NOTIFY")
        self.assertTrue(r["queue_required"])

    def test_margin_review_blocks_auto_kickoff(self):
        r=auto_kickoff(AutoKickoffEvidence(True,True,"LD_LAUNCH",True,"REVIEW"))
        self.assertEqual(r["reason"],"UNIT_ECONOMICS_REVIEW_REQUIRED")

    def test_material_integration_blocks(self):
        r=auto_kickoff(AutoKickoffEvidence(True,True,"LD_SYSTEM",True,"PASS",unverified_material_integration=True))
        self.assertEqual(r["status"],"HUMAN_GATE")

    def test_outcome_missing_criteria_enters_remediation(self):
        r=outcome_decision(OutcomeSnapshot(["login","report"],["login"],False,False))
        self.assertEqual(r["reason"],"OUTCOME_REMEDIATION_REQUIRED")
        self.assertEqual(r["missing"],["report"])

    def test_customer_acceptance_is_not_faked(self):
        r=outcome_decision(OutcomeSnapshot(["core-flow"],["core-flow"],True,False))
        self.assertEqual(r["reason"],"WAITING_CUSTOMER_ACCEPTANCE")
        self.assertFalse(r["outcome_pass"])

    def test_bounded_nonproduction_recovery_allowed(self):
        r=recovery_decision(RecoverySnapshot("BUILD_TEST_FAILURE",1,3,2.0,10.0,True))
        self.assertEqual(r["reason"],"BOUNDED_SELF_REPAIR_ALLOWED")

    def test_production_recovery_is_human_gate(self):
        r=recovery_decision(RecoverySnapshot("DEPLOY_FAILURE",0,3,1.0,10.0,True,production_impact=True))
        self.assertEqual(r["status"],"HUMAN_GATE")

    def test_no_idle_project(self):
        r=no_idle_check(ProjectState("BUILDING"))
        self.assertEqual(r["reason"],"IDLE_WITHOUT_DOCUMENTED_REASON")

    def test_documented_wait_is_valid(self):
        r=no_idle_check(ProjectState("BUILDING",blocker_reason="WAITING_CUSTOMER"))
        self.assertEqual(r["status"],"PASS")

if __name__=="__main__":
    unittest.main()
