import unittest
from validation_harness import run


class ControlledValidationTests(unittest.TestCase):
    def test_all_controlled_scenarios_pass(self):
        records = run()
        self.assertTrue(records)
        failures = [r.scenario for r in records if not r.passed]
        self.assertEqual(failures, [])

    def test_unknown_authority_holds(self):
        records = {r.scenario: r for r in run()}
        self.assertEqual(records["unknown authority fails closed"].actual, "HOLD")

    def test_production_boundary_escalates(self):
        records = {r.scenario: r for r in run()}
        self.assertEqual(records["production boundary escalates"].actual, "ESCALATE")

    def test_learning_is_propose_only(self):
        records = {r.scenario: r for r in run()}
        self.assertEqual(records["learning cannot auto-apply policy"].actual, "PROPOSE_ONLY")


if __name__ == "__main__":
    unittest.main()
