import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evaluate_outcome import build_learning_record, evaluate_outcome


class OutcomeLearningTests(unittest.TestCase):
    def test_missing_outcome_fails_closed(self):
        result = evaluate_outcome({})
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["policy_change_allowed"])

    def test_missing_evidence_fails_closed(self):
        result = evaluate_outcome({"outcome": "WON", "outcome_reason": "confirmed result"})
        self.assertEqual(result["learning_status"], "EVIDENCE_UNAVAILABLE")

    def test_terminal_with_evidence_is_ready(self):
        result = evaluate_outcome({
            "outcome": "LOST",
            "evidence_ref": "evidence-1",
            "outcome_reason": "confirmed result",
        })
        self.assertEqual(result["status"], "LOST")
        self.assertEqual(result["learning_status"], "READY")
        self.assertFalse(result["policy_change_allowed"])

    def test_non_terminal_is_signal(self):
        result = evaluate_outcome({
            "outcome": "MONITOR",
            "evidence_ref": "evidence-2",
            "outcome_reason": "awaiting change",
        })
        self.assertEqual(result["learning_status"], "NON_TERMINAL_SIGNAL")

    def test_learning_record_never_auto_applies(self):
        record = build_learning_record({
            "outcome": "NO_BID",
            "evidence_ref": "evidence-3",
            "outcome_reason": "human decision",
            "lesson": "Improve evidence collection",
            "policy_recommendation": "Review threshold",
        })
        self.assertEqual(record["policy_change_mode"], "HUMAN_REVIEW_ONLY")
        self.assertFalse(record["auto_apply"])


if __name__ == "__main__":
    unittest.main()
