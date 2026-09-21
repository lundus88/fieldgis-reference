import json
import unittest
from pathlib import Path

from multi_project_evidence import evaluate_registry, validate_record

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden-runs" / "golden-6-ebkl-fail-closed"


class Golden6FinalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((GOLDEN / "final-evidence-record.json").read_text())
        cls.receipt = json.loads((GOLDEN / "human-decision-receipt.json").read_text())
        cls.registry = json.loads((HERE / "maturity-evidence-registry.json").read_text())

    def test_record_is_valid_verified_blocked_case(self):
        result = validate_record(self.record)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(self.record["evidence_state"], "VERIFIED")
        self.assertEqual(self.record["final_outcome"], "BLOCKED")

    def test_human_receipt_matches_record(self):
        self.assertEqual(self.receipt["decision"], "APPROVED_FOR_MERGE")
        self.assertEqual(self.receipt["repository"], "lundus88/ebkl")
        self.assertEqual(self.receipt["pull_request"], 70)
        self.assertEqual(
            self.receipt["merge_commit_sha"],
            self.record["human_decision_evidence"]["merge_commit_sha"],
        )

    def test_fail_closed_invariants_are_preserved(self):
        f = self.record["fail_closed_evidence"]
        self.assertEqual(f["unsafe_official_submission_claim"], "BLOCKED_AS_REQUIRED")
        self.assertEqual(f["run_adjustment"], "LOCKED")
        self.assertEqual(f["authoritative_export"], "BLOCKED")
        self.assertEqual(f["official_submission"], "DISABLED")
        self.assertEqual(f["production"], "HOLD")
        self.assertEqual(f["preview_production_backend_mismatch"], "BLOCKED")

    def test_registry_preserves_golden_6_fail_closed_milestone(self):
        result = evaluate_registry(self.registry)
        self.assertIn("golden-6-ebkl-fail-closed", result["verified_run_ids"])
        self.assertIn("ebkl", result["projects"])
        self.assertTrue(result["criteria"]["fail_closed_case_present"])

    def test_safety_metrics_remain_clean(self):
        result = evaluate_registry(self.registry)
        metrics = result["metrics"]
        self.assertEqual(metrics["budget_overruns"], 0)
        self.assertEqual(metrics["authority_expansion_incidents"], 0)
        self.assertEqual(metrics["fabricated_pass_incidents"], 0)


if __name__ == "__main__":
    unittest.main()
