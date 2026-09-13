import unittest

from lom2_bounded_loop import build_plan, validate_execution, independent_validate


class TestLOM2BoundedLoop(unittest.TestCase):
    def base_goal(self):
        return {
            "goal_id": "g-1",
            "objective": "Prepare a non-production release candidate",
            "success_criteria": ["tests pass", "evidence recorded"],
            "risk_class": "MEDIUM",
            "delegation": {
                "allowed_actions": ["RUN_TEST", "GENERATE_ARTIFACT"],
                "forbidden_actions": ["PRODUCTION_DEPLOY"]
            },
            "requested_actions": ["RUN_TEST"],
            "evidence_required": ["test report"]
        }

    def test_safe_action_is_plannable(self):
        plan = build_plan(self.base_goal())
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["executable_actions"], ["RUN_TEST"])
        self.assertFalse(plan["requires_human"])

    def test_production_action_escalates(self):
        goal = self.base_goal()
        goal["requested_actions"] = ["PRODUCTION_DEPLOY"]
        plan = build_plan(goal)
        self.assertEqual(plan["status"], "ESCALATE")
        self.assertTrue(plan["requires_human"])
        self.assertIn("PRODUCTION_DEPLOY", plan["blocked_actions"])

    def test_unknown_authority_holds(self):
        goal = self.base_goal()
        goal["requested_actions"] = ["UNDECLARED_ACTION"]
        plan = build_plan(goal)
        self.assertEqual(plan["status"], "HOLD")
        self.assertIn("UNKNOWN_AUTHORITY", plan["reasons"])

    def test_missing_evidence_holds_execution(self):
        plan = build_plan(self.base_goal())
        result = validate_execution(plan, {"actor_role": "EXECUTOR", "action": "RUN_TEST", "evidence": []})
        self.assertEqual(result["verdict"], "HOLD")

    def test_independent_validation_passes_bounded_execution(self):
        plan = build_plan(self.base_goal())
        execution = {"actor_role": "EXECUTOR", "action": "RUN_TEST", "evidence": ["artifact://test-report"]}
        result = independent_validate(plan, execution, "VALIDATOR")
        self.assertEqual(result["verdict"], "PASS")

    def test_validator_cannot_be_replaced_by_executor(self):
        plan = build_plan(self.base_goal())
        execution = {"actor_role": "EXECUTOR", "action": "RUN_TEST", "evidence": ["artifact://test-report"]}
        result = independent_validate(plan, execution, "EXECUTOR")
        self.assertEqual(result["verdict"], "HOLD")


if __name__ == "__main__":
    unittest.main()
