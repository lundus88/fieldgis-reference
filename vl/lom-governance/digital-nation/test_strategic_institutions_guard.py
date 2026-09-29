import unittest
from pathlib import Path

from strategic_institutions_guard import load_registry, validate_registry, preview_decision

ROOT=Path(__file__).resolve().parent
REG=ROOT/"strategic-institutions-v1.json"

class StrategicInstitutionTests(unittest.TestCase):
    def test_registry_valid(self):
        self.assertEqual(validate_registry(load_registry(REG)),[])

    def test_preview_has_no_sovereign_or_production_authority(self):
        out=preview_decision(load_registry(REG))
        self.assertEqual(out["decision"],"ALLOW_PREVIEW_COMPOSITION")
        self.assertFalse(out["production_authority"])
        self.assertFalse(out["sovereign_authority"])

    def test_duplicate_engine_blocked(self):
        r=load_registry(REG)
        r["institutions"][0]["new_engine"]=True
        self.assertIn("UNAPPROVED_NEW_ENGINE:charter_policy_rights_registry",validate_registry(r))

    def test_ai_self_succession_boundary_required(self):
        r=load_registry(REG)
        r["hard_boundaries"].remove("No AI self-succession or self-authority expansion")
        self.assertIn("MISSING_HARD_BOUNDARY:No AI self-succession or self-authority expansion",validate_registry(r))

if __name__=="__main__":
    unittest.main()
