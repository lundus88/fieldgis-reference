#!/usr/bin/env python3
import json
import unittest
from pathlib import Path
from e2e_simulation import run_simulation

ROOT=Path(__file__).resolve().parent

class E2ESimulationTests(unittest.TestCase):
    def test_standard_order_reaches_delivery_without_post_payment_ld_human_start(self):
        order=json.loads((ROOT/"sample_order.json").read_text())
        r=run_simulation(order)
        self.assertEqual(r["final_state"],"DELIVERED")
        self.assertEqual(r["metrics"]["unexpected_failures"],0)
        self.assertEqual(r["metrics"]["idle_failures"],0)
        self.assertEqual(r["metrics"]["unsafe_authority_events"],0)
        self.assertFalse(r["production_executed"])
        self.assertIn("QUALIFIED_TO_BLUEPRINT_APPROVED",r["ld_human_gate_stages"])
        self.assertIn("BLUEPRINT_APPROVED_TO_QUOTATION_APPROVED",r["ld_human_gate_stages"])
        self.assertNotIn("PAYMENT_RECONCILED_TO_KICKOFF_APPROVED",r["ld_human_gate_stages"])

if __name__=="__main__":
    unittest.main()
