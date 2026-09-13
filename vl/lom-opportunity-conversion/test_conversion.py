import unittest

from evaluate_conversion import evaluate


class ConversionTests(unittest.TestCase):
    def test_watch_for_repeat_stays_watchlist(self):
        item = {
            "route": "WATCH_FOR_REPEAT",
            "next_evidence_action": "Monitor source."
        }
        self.assertEqual(evaluate(item)["decision"], "WATCHLIST")

    def test_missing_scope_or_value_fails_closed(self):
        item = {
            "route": "SUBCONTRACT_DISCOVERY",
            "survey_value_rm": None,
            "survey_scope": "UNCONFIRMED",
            "customer_intent": "UNCONFIRMED",
            "direct_bid_eligibility": "UNVERIFIED",
            "next_evidence_action": "Acquire evidence."
        }
        result = evaluate(item)
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("survey_value", result["reason"])
        self.assertIn("survey_scope", result["reason"])
        self.assertIn("customer_intent", result["reason"])
        self.assertIn("eligibility", result["reason"])

    def test_complete_minimum_evidence_can_continue(self):
        item = {
            "route": "DIRECT_BID",
            "survey_value_rm": 10000,
            "survey_scope": "CONFIRMED",
            "customer_intent": "CONFIRMED",
            "direct_bid_eligibility": "CONFIRMED",
            "next_evidence_action": "Score economics."
        }
        self.assertEqual(evaluate(item)["decision"], "CONTINUE")


if __name__ == "__main__":
    unittest.main()
