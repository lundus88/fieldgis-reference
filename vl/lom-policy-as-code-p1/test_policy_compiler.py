import copy
import json
import unittest
from pathlib import Path

from compile_policy_data import EXPECTED_AUTHORITY, build_projection

ROOT = Path(__file__).resolve().parent


class PolicyCompilerTests(unittest.TestCase):
    def test_projection_preserves_canonical_authority(self):
        projection = build_projection()["lom"]
        self.assertEqual(projection["policy_role"], "VERIFIER_ONLY")
        self.assertEqual(projection["authority"], EXPECTED_AUTHORITY)
        self.assertEqual(projection["execution_authority"], "NONE")
        self.assertTrue(projection["production_locked"])
        self.assertEqual(projection["live_policy_mutation"], "DISABLED")
        self.assertEqual(projection["opa_network_runtime"], "DISABLED")

    def test_snapshot_equals_canonical_compiler_output(self):
        expected = build_projection()
        actual = json.loads((ROOT / "policy-data.json").read_text())
        self.assertEqual(actual, expected)

    def test_human_only_actions_include_critical_commitments(self):
        actions = set(build_projection()["lom"]["human_only_actions"])
        for action in (
            "PROTECTED_MAIN_MERGE",
            "PRODUCTION_RELEASE",
            "AUTHORITY_WIDENING",
            "AUTH_SECURITY_POLICY_CHANGE",
            "CUSTOMER_COMMITMENT",
            "BID_SUBMISSION",
            "PRICING_COMMITMENT",
            "CONTRACT_COMMITMENT",
            "FINANCIAL_COMMITMENT",
        ):
            self.assertIn(action, actions)

    def test_bounded_actions_are_non_production_projection_only(self):
        projection = build_projection()["lom"]
        self.assertGreater(len(projection["bounded_actions"]), 0)
        ids = {item["action_id"] for item in projection["bounded_actions"]}
        self.assertIn("RUN_TEST", ids)
        self.assertNotIn("PRODUCTION_RELEASE", ids)

    def test_projection_digest_detects_tamper(self):
        projection = build_projection()["lom"]
        tampered = copy.deepcopy(projection)
        tampered["authority"]["production_authority"] = "AUTO"
        self.assertNotEqual(tampered, projection)


if __name__ == "__main__":
    unittest.main()
