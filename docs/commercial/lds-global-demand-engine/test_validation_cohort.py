#!/usr/bin/env python3
import unittest
from validation_cohort import Cohort,evaluate_cohort

class ValidationCohortTests(unittest.TestCase):
    def test_initial_target_can_be_measured_without_granting_scale(self):
        r=evaluate_cohort(Cohort(100,10,4,1,1,0,0,1,0))
        self.assertTrue(r["validation_target_reached"]["paid_customer_1"])
        self.assertFalse(r["scale_authority"])
        self.assertEqual(r["production_authority"],"HUMAN_ONLY")

    def test_largest_leak_is_identified(self):
        r=evaluate_cohort(Cohort(100,20,10,1,1))
        self.assertEqual(r["largest_material_leak"],"quotation_to_paid")

    def test_cost_per_qualified_lead_requires_attribution(self):
        r=evaluate_cohort(Cohort(100,10,4,1,1,spend=500))
        self.assertEqual(r["cost_per_qualified_lead"],50.0)

if __name__=="__main__":
    unittest.main()
