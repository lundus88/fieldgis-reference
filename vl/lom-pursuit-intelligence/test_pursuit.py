import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("evaluate_pursuit.py")
spec = importlib.util.spec_from_file_location("evaluate_pursuit", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
evaluate = module.evaluate


class PursuitTests(unittest.TestCase):
    def test_watch_signal_stays_watchlist(self):
        item = {"route": "WATCH_FOR_REPEAT", "next_evidence_action": "Refresh evidence."}
        self.assertEqual(evaluate(item)["decision"], "WATCHLIST")

    def test_missing_evidence_fails_closed(self):
        item = {
            "route": "SUBCONTRACT_DISCOVERY",
            "target_identity": "UNCONFIRMED",
            "scope_status": "UNCONFIRMED",
            "economic_fit": "UNKNOWN",
            "deadline_status": "ACTIVE",
            "eligibility": "UNCONFIRMED",
            "intent": "UNCONFIRMED",
        }
        result = evaluate(item)
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("target identity", result["reason"])
        self.assertIn("scope", result["reason"])
        self.assertIn("economic fit", result["reason"])
        self.assertIn("eligibility", result["reason"])
        self.assertIn("intent", result["reason"])

    def test_minimum_evidence_can_continue(self):
        item = {
            "route": "DIRECT_BID",
            "target_identity": "CONFIRMED",
            "scope_status": "CONFIRMED",
            "economic_fit": "SUPPORTED",
            "deadline_status": "ACTIVE",
            "eligibility": "CONFIRMED",
            "intent": "CONFIRMED",
        }
        self.assertEqual(evaluate(item)["decision"], "CONTINUE")


if __name__ == "__main__":
    unittest.main()
