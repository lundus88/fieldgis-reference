#!/usr/bin/env python3
import unittest
from support_plan_engine import *

def p(**kw):
    d=dict(plan_key="ESSENTIAL_CARE",commercially_approved=True,response_target_evidenced=False,
      resolution_target_evidenced=False,recurring_price_approved=True,customer_accepted=True,
      third_party_costs_disclosed=True,cancellation_terms_disclosed=True)
    d.update(kw); return SupportPlan(**d)

class SupportPlanTests(unittest.TestCase):
    def test_unknown_plan_holds(self):
        self.assertEqual(assess(p(plan_key="X"))["status"],"HOLD")
    def test_customer_acceptance_required(self):
        self.assertEqual(assess(p(customer_accepted=False))["status"],"CUSTOMER_DECISION")
    def test_unproven_sla_not_advertised(self):
        r=assess(p())
        self.assertFalse(r["advertise_response_target"])
        self.assertFalse(r["advertise_resolution_target"])
    def test_defect_not_enhancement(self):
        self.assertFalse(classify_request(False,True,False,False)["billable_enhancement"])
    def test_security_escalates(self):
        self.assertEqual(classify_request(False,False,True,False)["route"],"HUMAN_SECURITY_ESCALATION")
    def test_enhancement_routes_to_change_request(self):
        self.assertTrue(classify_request(False,False,False,True)["billable_enhancement"])

if __name__=="__main__": unittest.main()
