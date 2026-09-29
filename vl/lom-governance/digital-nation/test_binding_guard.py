import json
import unittest
from pathlib import Path

from binding_guard import activation_decision, validate_manifest


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "adapter-bindings-v1.json"


class BindingGuardTests(unittest.TestCase):
    def _manifest(self):
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_current_manifest_is_structurally_valid(self):
        self.assertEqual(validate_manifest(self._manifest()), [])

    def test_current_manifest_holds_only_on_unmerged_economic_participation(self):
        decision = activation_decision(self._manifest())
        self.assertEqual(decision["decision"], "HOLD")
        self.assertEqual(decision["hold_bindings"], ["economic_participation"])
        self.assertFalse(decision["production_authority"])

    def test_new_preview_owners_are_bound(self):
        m = self._manifest()
        by_id = {x["id"]: x for x in m["bindings"]}
        self.assertEqual(by_id["education_skill"]["binding_status"], "BOUND_PREVIEW")
        self.assertEqual(by_id["education_skill"]["owner"], "LOM Education")
        self.assertEqual(by_id["reputation"]["binding_status"], "BOUND_PREVIEW")
        self.assertEqual(by_id["reputation"]["owner"], "LOM Trust")
        self.assertEqual(by_id["dispute"]["binding_status"], "BOUND_PREVIEW")
        self.assertEqual(by_id["dispute"]["owner"], "LOM Trust")

    def test_pending_dependency_cannot_pretend_to_be_main(self):
        m = self._manifest()
        b = next(x for x in m["bindings"] if x["id"] == "economic_participation")
        b["source_ref"] = "main"
        errors = validate_manifest(m)
        self.assertIn("PENDING_DEPENDENCY_CANNOT_BIND_MAIN:economic_participation", errors)

    def test_preview_binding_cannot_grant_production(self):
        m = self._manifest()
        m["bindings"][0]["production_authorized"] = True
        errors = validate_manifest(m)
        self.assertTrue(any(e.startswith("PRODUCTION_AUTHORITY_MUST_BE_FALSE:") for e in errors))

    def test_unresolved_owner_marker_is_enforced_when_used(self):
        m = self._manifest()
        b = next(x for x in m["bindings"] if x["id"] == "education_skill")
        b["binding_status"] = "HOLD_UNRESOLVED_OWNER"
        b["owner"] = "invented-owner"
        b["source_repo"] = None
        b["source_ref"] = None
        b["source_path"] = None
        errors = validate_manifest(m)
        self.assertIn("UNRESOLVED_OWNER_MARKER_REQUIRED:education_skill", errors)


if __name__ == "__main__":
    unittest.main()
