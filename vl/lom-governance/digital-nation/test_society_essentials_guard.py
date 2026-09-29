import unittest
from pathlib import Path

from society_essentials_guard import load_registry, validate_registry, preview_decision

ROOT=Path(__file__).resolve().parent
REG=ROOT/"society-essentials-v1.json"

class SocietyEssentialsTests(unittest.TestCase):
    def test_registry_valid(self):
        self.assertEqual(validate_registry(load_registry(REG)),[])

    def test_preview_only(self):
        out=preview_decision(load_registry(REG))
        self.assertEqual(out["decision"],"ALLOW_PREVIEW_COMPOSITION")
        self.assertFalse(out["production_authority"])

    def test_duplicate_engine_blocked(self):
        r=load_registry(REG)
        r["capabilities"][0]["new_engine"]=True
        self.assertIn("UNAPPROVED_NEW_ENGINE:world_search_navigation",validate_registry(r))

    def test_reuse_required(self):
        r=load_registry(REG)
        r["capabilities"][0]["reuse"]=[]
        self.assertIn("REUSE_REQUIRED:world_search_navigation",validate_registry(r))

if __name__=="__main__":
    unittest.main()
