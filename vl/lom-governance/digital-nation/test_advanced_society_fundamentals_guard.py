import unittest
from pathlib import Path
from advanced_society_fundamentals_guard import load_registry, validate_registry, preview_decision

ROOT=Path(__file__).resolve().parent
REG=ROOT/"advanced-society-fundamentals-v1.json"

class AdvancedSocietyFundamentalsTests(unittest.TestCase):
    def test_exactly_twelve_fundamentals(self):
        r=load_registry(REG)
        self.assertEqual(len(r["pillars"]),12)
        self.assertEqual(validate_registry(r),[])

    def test_preview_has_no_sovereign_or_production_authority(self):
        out=preview_decision(load_registry(REG))
        self.assertEqual(out["decision"],"ALLOW_PREVIEW_COMPOSITION")
        self.assertFalse(out["production_authority"])
        self.assertFalse(out["sovereign_authority"])

    def test_missing_pillar_fails_closed(self):
        r=load_registry(REG)
        r["pillars"]=r["pillars"][:-1]
        self.assertIn("TWELVE_PILLAR_SET_OR_ORDER_MISMATCH",validate_registry(r))

    def test_authority_bypass_boundary_is_mandatory(self):
        r=load_registry(REG)
        r["hard_boundaries"].remove("No person or AI bypasses active authority evidence and audit controls")
        self.assertIn(
            "MISSING_HARD_BOUNDARY:No person or AI bypasses active authority evidence and audit controls",
            validate_registry(r)
        )

if __name__=="__main__":
    unittest.main()
