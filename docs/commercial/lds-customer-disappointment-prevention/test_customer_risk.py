#!/usr/bin/env python3
import unittest
from customer_risk import Signal,evaluate,should_send_status,detect_silent_dissatisfaction,detect_handoff_context_loss,assess_support_sla,detect_adoption_failure,assess_cost_surprise,verify_delivery_success,assess_update_regression,reconcile_state,assess_agent_budget,assess_portability,assess_internal_failure_charge

class CustomerRiskTests(unittest.TestCase):
    def test_clear(self):
        self.assertEqual(evaluate([])["status"],"CLEAR")

    def test_p0_forces_human_escalation(self):
        r=evaluate([Signal("CDP-010","P0",True,("incident-1",))])
        self.assertIn("HUMAN_ESCALATION",r["actions"])
        self.assertIn("FREEZE_CONSEQUENTIAL_AUTOMATION",r["actions"])

    def test_active_risk_without_evidence_holds(self):
        r=evaluate([Signal("CDP-002","P1",True,())])
        self.assertEqual(r["status"],"HOLD")

    def test_customer_dependency_rebaselines_eta(self):
        r=evaluate([Signal("CDP-004","P2",True,("dep-1",))])
        self.assertIn("REBASELINE_ETA",r["actions"])
        self.assertIn("SET_CLIENT_ACTION_REQUIRED",r["actions"])

    def test_p1_gets_owner_and_client_update(self):
        r=evaluate([Signal("CDP-007","P1",True,("ticket-7",))])
        self.assertIn("OWNER_ASSIGN",r["actions"])
        self.assertIn("CLIENT_STATUS_UPDATE",r["actions"])

    def test_status_update_cadence(self):
        self.assertTrue(should_send_status(4,True))
        self.assertFalse(should_send_status(3,True))
        self.assertTrue(should_send_status(24,False))

    def test_silent_dissatisfaction_detected_without_complaint(self):
        r=detect_silent_dissatisfaction("NO_RESPONSE",2,0)
        self.assertTrue(r["active"])
        self.assertEqual(r["risk_id"],"CDP-017")

    def test_handoff_context_loss_detected(self):
        r=detect_handoff_context_loss(True,False,True)
        self.assertTrue(r["active"])
        self.assertEqual(r["action"],"RESTORE_CONTEXT_BEFORE_REPLY")

    def test_response_met_but_resolution_breached(self):
        r=assess_support_sla(1,2,30,24,False)
        self.assertTrue(r["response_sla_met"])
        self.assertFalse(r["resolution_sla_met"])
        self.assertEqual(r["risk_id"],"CDP-019")

    def test_uat_pass_does_not_equal_adoption_success(self):
        r=detect_adoption_failure(True,False,False,1)
        self.assertTrue(r["active"])
        self.assertEqual(r["action"],"ADOPTION_CHECKPOINT")

    def test_unapproved_cost_increase_is_blocked(self):
        r=assess_cost_surprise(1000,1200,False)
        self.assertTrue(r["active"])
        self.assertEqual(r["action"],"BLOCK_EXTRA_CHARGE")

    def test_deploy_command_alone_is_not_delivery_success(self):
        r=verify_delivery_success(True,False,True,True)
        self.assertFalse(r["delivery_complete"])
        self.assertEqual(r["action"],"BLOCK_COMPLETE_CLAIM")

    def test_update_without_regression_is_blocked(self):
        r=assess_update_regression(True,True,False)
        self.assertTrue(r["active"])

    def test_state_divergence_fails_closed(self):
        r=reconcile_state({"payment":"PAID","portal":"PENDING","support":"PAID"},"payment")
        self.assertTrue(r["active"])
        self.assertEqual(r["action"],"FAIL_CLOSED_AND_RECONCILE")

    def test_agent_loop_hits_kill_switch(self):
        r=assess_agent_budget(10,10,3,3,5.0,10.0,30,60,True)
        self.assertTrue(r["active"])
        self.assertEqual(r["action"],"KILL_AND_HOLD")

    def test_missing_exit_artifact_blocks_handover(self):
        r=assess_portability(True,True,False,True)
        self.assertTrue(r["active"])
        self.assertEqual(r["action"],"BLOCK_FINAL_HANDOVER")

    def test_internal_failure_cannot_be_extra_charge(self):
        r=assess_internal_failure_charge(True,True,False,False)
        self.assertTrue(r["active"])
        self.assertEqual(r["action"],"BLOCK_CHARGE_AND_HUMAN_REVIEW")

if __name__=="__main__":
    unittest.main()
