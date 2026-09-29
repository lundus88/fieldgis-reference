import unittest
from pathlib import Path

from foundational_gaps_guard import load_registry, validate_registry, preview_decision

ROOT=Path(__file__).resolve().parent
REG=ROOT/"foundational-gaps-closure-v1.json"

class FoundationalGapsGuardTests(unittest.TestCase):
    def test_complete_foundation_set(self):
        r=load_registry(REG)
        self.assertEqual(len(r["capabilities"]),8)
        self.assertEqual(validate_registry(r),[])

    def test_preview_only(self):
        out=preview_decision(load_registry(REG))
        self.assertEqual(out["decision"],"ALLOW_PREVIEW_COMPOSITION")
        self.assertFalse(out["production_authority"])
        self.assertFalse(out["live_financial_authority"])

    def test_duplicate_engine_is_blocked(self):
        r=load_registry(REG)
        r["capabilities"][0]["new_engine"]=True
        self.assertIn("UNAPPROVED_NEW_ENGINE:persistent_world_state_runtime",validate_registry(r))

    def test_jurisdiction_fail_closed_rule_is_mandatory(self):
        r=load_registry(REG)
        r["invariants"].remove("Unsupported or unknown jurisdiction conditions fail to MANUAL_REVIEW.")
        self.assertIn(
            "MISSING_INVARIANT:Unsupported or unknown jurisdiction conditions fail to MANUAL_REVIEW.",
            validate_registry(r)
        )

    def test_synthetic_evidence_boundary_is_mandatory(self):
        r=load_registry(REG)
        r["invariants"].remove("Synthetic evidence is never real-world evidence.")
        self.assertIn(
            "MISSING_INVARIANT:Synthetic evidence is never real-world evidence.",
            validate_registry(r)
        )

if __name__=="__main__":
    unittest.main()
