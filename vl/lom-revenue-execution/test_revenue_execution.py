import unittest
from score_opportunity import score


class RevenueExecutionTests(unittest.TestCase):
    def test_missing_evidence_holds(self):
        result = score({})
        self.assertEqual(result["decision"], "HOLD")
        self.assertIsNone(result["score"])

    def test_stale_evidence_reviews(self):
        result = score({"evidence_refs": ["x"], "evidence_status": "STALE"})
        self.assertEqual(result["decision"], "REVIEW")

    def test_high_value_accelerates(self):
        result = score({
            "revenue_potential": 100,
            "probability_of_success": 100,
            "strategic_value": 100,
            "urgency": 100,
            "delivery_risk": 0,
            "effort_cost": 0,
            "evidence_status": "FRESH",
            "evidence_refs": ["x"]
        })
        self.assertEqual(result["decision"], "ACCELERATE")
        self.assertEqual(result["score"], 75.0)

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            score({
                "revenue_potential": 101,
                "probability_of_success": 50,
                "strategic_value": 50,
                "urgency": 50,
                "delivery_risk": 50,
                "effort_cost": 50,
                "evidence_status": "FRESH",
                "evidence_refs": ["x"]
            })


if __name__ == "__main__":
    unittest.main()
