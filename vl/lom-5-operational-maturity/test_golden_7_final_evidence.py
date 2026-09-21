import json
import unittest
from pathlib import Path

from multi_project_evidence import evaluate_registry, validate_record

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden-runs" / "golden-7-lunduslead-remediation"


class Golden7FinalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((GOLDEN / "final-evidence-record.json").read_text())
        cls.receipt = json.loads((GOLDEN / "human-decision-receipt.json").read_text())
        cls.registry = json.loads((HERE / "maturity-evidence-registry.json").read_text())

    def test_record_is_valid_verified_remediation(self):
        result = validate_record(self.record)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(self.record["evidence_state"], "VERIFIED")
        self.assertEqual(self.record["final_outcome"], "REMEDIATED")
        self.assertTrue(self.record["remediation_history"])

    def test_human_receipt_matches_record(self):
        self.assertEqual(self.receipt["decision"], "APPROVED_FOR_MERGE")
        self.assertEqual(self.receipt["repository"], "lundus88/lundus-lead")
        self.assertEqual(self.receipt["pull_request"], 155)
        self.assertEqual(
            self.receipt["merge_commit_sha"],
            self.record["human_decision_evidence"]["merge_commit_sha"],
        )

    def test_registry_preserves_golden_7_project_and_remediation_milestones(self):
        result = evaluate_registry(self.registry)
        self.assertIn("golden-7-lunduslead-remediation", result["verified_run_ids"])
        self.assertEqual(sorted(result["projects"]), ["ebkl", "lom", "lunduslead"])
        self.assertTrue(result["criteria"]["at_least_three_projects"])
        self.assertTrue(result["criteria"]["remediation_case_present"])
        self.assertTrue(result["criteria"]["fail_closed_case_present"])

    def test_safety_metrics_remain_clean(self):
        result = evaluate_registry(self.registry)
        self.assertEqual(result["metrics"]["budget_overruns"], 0)
        self.assertEqual(result["metrics"]["authority_expansion_incidents"], 0)
        self.assertEqual(result["metrics"]["fabricated_pass_incidents"], 0)


if __name__ == "__main__":
    unittest.main()
