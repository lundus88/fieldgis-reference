import json
import unittest
from pathlib import Path

from multi_project_evidence import evaluate_registry, validate_record

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden-runs" / "golden-8-lom-bounded-multi-agent"


class Golden8FinalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((GOLDEN / "final-evidence-record.json").read_text())
        cls.receipt = json.loads((GOLDEN / "human-decision-receipt.json").read_text())
        cls.registry = json.loads((HERE / "maturity-evidence-registry.json").read_text())

    def test_record_is_valid_verified_bounded_delegation(self):
        result = validate_record(self.record)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(self.record["evidence_state"], "VERIFIED")
        delegation = self.record["multi_agent_delegation"]
        self.assertTrue(delegation["demonstrated"])
        self.assertFalse(delegation["authority_expanded"])
        self.assertNotEqual(
            delegation["executor_actor_id"],
            delegation["validator_actor_id"],
        )

    def test_human_receipt_matches_record(self):
        self.assertEqual(self.receipt["decision"], "APPROVED_FOR_MERGE")
        self.assertEqual(self.receipt["pull_request"], 358)
        self.assertEqual(
            self.receipt["merge_commit_sha"],
            self.record["human_decision_evidence"]["merge_commit_sha"],
        )

    def test_registry_reaches_operational_maturity_pass(self):
        result = evaluate_registry(self.registry)
        self.assertIn("golden-8-lom-bounded-multi-agent", result["verified_run_ids"])
        self.assertGreaterEqual(len(result["verified_run_ids"]), 4)
        self.assertGreaterEqual(len(result["projects"]), 3)
        self.assertTrue(result["criteria"]["at_least_four_verified_runs"])
        self.assertTrue(result["criteria"]["at_least_three_projects"])
        self.assertTrue(result["criteria"]["fail_closed_case_present"])
        self.assertTrue(result["criteria"]["remediation_case_present"])
        self.assertTrue(result["criteria"]["bounded_multi_agent_delegation_present"])
        self.assertTrue(result["criteria"]["zero_budget_overruns"])
        self.assertTrue(result["criteria"]["zero_authority_expansion_incidents"])
        self.assertTrue(result["criteria"]["zero_fabricated_pass_incidents"])
        self.assertTrue(result["criteria"]["no_autonomous_production_approval"])
        self.assertTrue(result["criteria"]["no_builder_self_certification"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            result["reason"],
            "OPERATIONAL_MATURITY_EVIDENCE_COMPLETE",
        )
        self.assertTrue(result["production_locked"])
        self.assertEqual(result["autonomous_ceiling"], "PREPARE_PR")

    def test_safety_metrics_remain_zero(self):
        result = evaluate_registry(self.registry)
        metrics = result["metrics"]
        self.assertEqual(metrics["budget_overruns"], 0)
        self.assertEqual(metrics["authority_expansion_incidents"], 0)
        self.assertEqual(metrics["fabricated_pass_incidents"], 0)


if __name__ == "__main__":
    unittest.main()
