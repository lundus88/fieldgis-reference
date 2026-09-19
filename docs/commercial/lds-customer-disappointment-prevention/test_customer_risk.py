#!/usr/bin/env python3
import unittest
from customer_risk import Signal,evaluate,should_send_status

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

if __name__=="__main__":
    unittest.main()
