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

    def test_current_manifest_holds_on_real_gaps(self):
        decision = activation_decision(self._manifest())
        self.assertEqual(decision["decision"], "HOLD")
        self.assertIn("economic_participation", decision["hold_bindings"])
        self.assertIn("education_skill", decision["hold_bindings"])
        self.assertIn("reputation", decision["hold_bindings"])
        self.assertFalse(decision["production_authority"])

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

    def test_unresolved_owner_must_remain_explicit(self):
        m = self._manifest()
        b = next(x for x in m["bindings"] if x["id"] == "education_skill")
        b["owner"] = "invented-owner"
        errors = validate_manifest(m)
        self.assertIn("UNRESOLVED_OWNER_MARKER_REQUIRED:education_skill", errors)


if __name__ == "__main__":
    unittest.main()
