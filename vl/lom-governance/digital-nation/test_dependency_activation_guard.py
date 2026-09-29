import unittest

from dependency_activation_guard import validate_dependency_evidence


class DependencyActivationGuardTests(unittest.TestCase):
    def _evidence(self):
        return {
            "pr_number": 425,
            "merged": True,
            "merge_commit_sha": "abc123",
            "verified_ref": "main",
            "exact_main": True,
            "checks": [
                {"name": "LOM Economic Participation P0", "conclusion": "success"},
                {"name": "VL Governance CI", "conclusion": "success"},
                {"name": "LOM Master Compliance", "conclusion": "success"},
                {"name": "LOM Level 6 Exact-Main Regression", "conclusion": "success"},
            ],
        }

    def test_complete_exact_main_evidence_is_eligible(self):
        out = validate_dependency_evidence(self._evidence())
        self.assertEqual(out["decision"], "ELIGIBLE_FOR_BOUND_PREVIEW_UPDATE")
        self.assertFalse(out["production_authority"])
        self.assertFalse(out["merge_authority"])

    def test_unmerged_pr_holds(self):
        e = self._evidence()
        e["merged"] = False
        out = validate_dependency_evidence(e)
        self.assertEqual(out["decision"], "HOLD")
        self.assertIn("PR_NOT_MERGED", out["errors"])

    def test_missing_exact_main_check_holds(self):
        e = self._evidence()
        e["checks"] = [x for x in e["checks"] if x["name"] != "LOM Economic Participation P0"]
        out = validate_dependency_evidence(e)
        self.assertEqual(out["decision"], "HOLD")
        self.assertIn("CHECK_NOT_SUCCESS:LOM Economic Participation P0", out["errors"])


if __name__ == "__main__":
    unittest.main()
