import json
import unittest
from pathlib import Path

from multi_project_evidence import evaluate_registry, validate_record

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden-runs" / "golden-5-lom-capture-v2"


class Golden5FinalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((GOLDEN / "final-evidence-record.json").read_text())
        cls.receipt = json.loads((GOLDEN / "human-decision-receipt.json").read_text())
        cls.registry = json.loads((HERE / "maturity-evidence-registry.json").read_text())

    def test_final_record_is_valid_verified_evidence(self):
        result = validate_record(self.record)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(self.record["evidence_state"], "VERIFIED")

    def test_human_receipt_matches_final_record(self):
        self.assertEqual(self.receipt["decision"], "APPROVED_FOR_MERGE")
        self.assertEqual(self.receipt["pull_request"], 352)
        self.assertEqual(
            self.receipt["merge_commit_sha"],
            self.record["human_decision_evidence"]["merge_commit_sha"],
        )
        self.assertEqual(
            self.receipt["review_id"],
            self.record["human_decision_evidence"]["review_id"],
        )

    def test_safety_invariants_remain_zero_or_false(self):
        for key in (
            "budget_overrun",
            "authority_expansion_incident",
            "fabricated_pass_incident",
            "production_approval",
            "builder_self_certified",
        ):
            self.assertFalse(self.record[key], key)
        self.assertFalse(self.record["multi_agent_delegation"]["authority_expanded"])

    def test_registry_counts_golden_5_but_issue_158_stays_hold(self):
        result = evaluate_registry(self.registry)
        self.assertIn("golden-5-lom-capture-v2", result["verified_run_ids"])
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "OPERATIONAL_MATURITY_EVIDENCE_INCOMPLETE")
        self.assertFalse(result["criteria"]["at_least_four_verified_runs"])

    def test_original_execution_identity_is_preserved(self):
        self.assertEqual(
            self.record["source_commit_sha"],
            "492690fc947659d30fc33139669f8a363cca3aaa",
        )
        self.assertEqual(
            self.record["qa_security_evidence"][0]["run_id"],
            "35553700124",
        )
        self.assertEqual(self.record["attempts"], 1)
        self.assertEqual(self.record["estimated_model_tool_cost"], 0.0)


if __name__ == "__main__":
    unittest.main()
