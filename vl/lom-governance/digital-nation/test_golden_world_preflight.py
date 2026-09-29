import json
import unittest
from pathlib import Path

from golden_world_preflight import preview_preflight


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "adapter-bindings-v1.json"


class GoldenWorldPreflightTests(unittest.TestCase):
    def _manifest(self):
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_current_preflight_holds_on_economic_participation_dependency(self):
        out = preview_preflight(self._manifest())
        self.assertEqual(out["decision"], "HOLD")
        self.assertEqual(out["hold_bindings"], ["economic_participation"])
        self.assertIn("economic_participation", out["not_preview_bound"])
        self.assertFalse(out["production_authority"])
        self.assertFalse(out["live_payment_authority"])
        self.assertFalse(out["live_payout_authority"])

    def test_preflight_becomes_preview_ready_only_when_dependency_is_bound(self):
        m = self._manifest()
        ep = next(x for x in m["bindings"] if x["id"] == "economic_participation")
        ep["binding_status"] = "BOUND_PREVIEW"
        ep.pop("dependency_pr", None)
        ep["source_ref"] = "main"
        out = preview_preflight(m)
        self.assertEqual(out["decision"], "READY_FOR_SYNTHETIC_GOLDEN_JOURNEY")
        self.assertEqual(out["hold_bindings"], [])
        self.assertEqual(out["not_preview_bound"], [])
        self.assertFalse(out["production_authority"])

    def test_missing_required_binding_fails_closed(self):
        m = self._manifest()
        m["bindings"] = [x for x in m["bindings"] if x["id"] != "payment"]
        out = preview_preflight(m)
        self.assertEqual(out["decision"], "HOLD")
        self.assertIn("MISSING_REQUIRED_BINDING:payment", out["errors"])


if __name__ == "__main__":
    unittest.main()
