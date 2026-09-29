import json
import unittest
from pathlib import Path

from golden_world_preview_runner import run_synthetic_golden_world


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "adapter-bindings-v1.json"


class GoldenWorldPreviewRunnerTests(unittest.TestCase):
    def _manifest(self):
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_current_manifest_refuses_full_journey(self):
        out = run_synthetic_golden_world(self._manifest())
        self.assertEqual(out["decision"], "HOLD")
        self.assertEqual(out["reason"], "PREFLIGHT_NOT_READY")
        self.assertFalse(out["production_authority"])

    def test_in_memory_post_merge_fixture_can_prove_journey(self):
        m = self._manifest()
        ep = next(x for x in m["bindings"] if x["id"] == "economic_participation")
        ep["binding_status"] = "BOUND_PREVIEW"
        ep["source_ref"] = "main"
        ep.pop("dependency_pr", None)

        out = run_synthetic_golden_world(m)
        self.assertEqual(out["decision"], "PASS")
        self.assertEqual(out["event_count"], 12)
        self.assertFalse(out["production_authority"])
        self.assertFalse(out["live_payment_authority"])
        self.assertFalse(out["live_payout_authority"])
        self.assertFalse(out["real_customer_evidence"])
        self.assertFalse(out["real_revenue_evidence"])
        self.assertFalse(out["real_worker_evidence"])

    def test_synthetic_preview_never_claims_real_evidence(self):
        m = self._manifest()
        ep = next(x for x in m["bindings"] if x["id"] == "economic_participation")
        ep["binding_status"] = "BOUND_PREVIEW"
        ep["source_ref"] = "main"
        ep.pop("dependency_pr", None)

        out = run_synthetic_golden_world(m)
        self.assertNotIn("production_ready", out)
        self.assertFalse(out["real_customer_evidence"])
        self.assertFalse(out["real_revenue_evidence"])


if __name__ == "__main__":
    unittest.main()
