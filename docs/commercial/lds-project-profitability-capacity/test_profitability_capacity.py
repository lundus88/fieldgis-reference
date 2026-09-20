#!/usr/bin/env python3
import unittest
from profitability_capacity import *

class ProfitabilityCapacityTests(unittest.TestCase):
    def test_internal_rework_reduces_margin(self):
        e=ProjectEconomics(revenue_minor=100000,rework_minor=30000)
        r=profitability(e)
        self.assertEqual(r["contribution_minor"],70000)
    def test_stale_inputs_never_healthy(self):
        e=ProjectEconomics(revenue_minor=100000,inputs_current=False)
        self.assertEqual(profitability(e)["status"],"REVIEW")
    def test_loss_project_at_risk(self):
        e=ProjectEconomics(revenue_minor=100000,human_effort_minor=120000)
        self.assertEqual(profitability(e)["status"],"AT_RISK")
    def test_no_auto_price_or_reject(self):
        r=profitability(ProjectEconomics(revenue_minor=100000,human_effort_minor=120000))
        self.assertFalse(r["auto_price_change"])
        self.assertFalse(r["auto_customer_reject"])
    def test_critical_incident_reserves_capacity(self):
        c=Capacity(5,2,20,1,100,20,10)
        self.assertEqual(capacity_decision(c)["status"],"HOLD_CAPACITY")
    def test_requested_capacity_over_available_holds(self):
        c=Capacity(5,2,20,0,50,20,40)
        self.assertFalse(capacity_decision(c)["schedulable"])
    def test_healthy_capacity_schedulable(self):
        c=Capacity(3,1,20,0,100,20,30)
        self.assertTrue(capacity_decision(c)["schedulable"])

    def test_daily_paid_order_cap_is_three(self):
        r=daily_order_intake(2)
        self.assertTrue(r["accept_new_paid_order"])
        self.assertEqual(r["remaining_slots"],1)

    def test_fourth_order_waitlists_not_rejects(self):
        r=daily_order_intake(3)
        self.assertEqual(r["status"],"WAITLIST")
        self.assertFalse(r["automatic_reject"])
        self.assertEqual(r["customer_action"],"NEXT_AVAILABLE_SLOT")

    def test_capacity_pressure_can_hold_before_daily_cap(self):
        r=daily_order_intake(1,qa_queue=4,overdue_jobs=2)
        self.assertEqual(r["status"],"REVIEW")
        self.assertFalse(r["accept_new_paid_order"])

    def test_cap_never_auto_increases(self):
        r=cap_change_authority(30,"STAGE_1")
        self.assertTrue(r["evidence_sufficient"])
        self.assertEqual(r["suggested_next_cap"],5)
        self.assertFalse(r["automatic_change"])
        self.assertEqual(r["authority"],"HUMAN_ONLY")

if __name__=="__main__": unittest.main()
