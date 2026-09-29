import unittest
from pathlib import Path
from high_value_guard import load_registry, validate_high_value_registry, decision

ROOT=Path(__file__).resolve().parent
REG=ROOT/"high-value-layer-v1.json"

class HighValueGuardTests(unittest.TestCase):
    def test_registry_valid(self):
        self.assertEqual(validate_high_value_registry(load_registry(REG)),[])

    def test_preview_only(self):
        out=decision(load_registry(REG))
        self.assertEqual(out["decision"],"ALLOW_PREVIEW_COMPOSITION")
        self.assertFalse(out["production_authority"])

    def _capability(self, registry, capability_id):
        return next(item for item in registry["capabilities"] if item["id"] == capability_id)

    def test_duplicate_engine_fails(self):
        r=load_registry(REG)
        self._capability(r, "member_economic_passport")["new_engine"]=True
        self.assertIn("UNAPPROVED_NEW_ENGINE:member_economic_passport",validate_high_value_registry(r))

    def test_reuse_is_mandatory(self):
        r=load_registry(REG)
        self._capability(r, "member_economic_passport")["reuse"]=[]
        self.assertIn("REUSE_REQUIRED:member_economic_passport",validate_high_value_registry(r))

if __name__=="__main__":
    unittest.main()
