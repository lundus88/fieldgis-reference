import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("render_brief.py")
spec = importlib.util.spec_from_file_location("render_brief", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
render = module.render


class DailyPursuitBriefTests(unittest.TestCase):
    def test_missing_queue_fails_closed(self):
        result = render(None)
        self.assertEqual(result["status"], "EVIDENCE_UNAVAILABLE")

    def test_attention_and_monitor_summary(self):
        queue = [
            {"queue_rank": 1, "director_action": "REVIEW_PURSUIT", "pursuit_decision": "CONTINUE", "urgency_score": 80, "evidence_gap_count": 0, "next_best_action": "Review."},
            {"queue_rank": 2, "director_action": "ACQUIRE_EVIDENCE", "pursuit_decision": "HOLD", "urgency_score": 90, "evidence_gap_count": 2, "next_best_action": "Verify."},
            {"queue_rank": 3, "director_action": "MONITOR", "pursuit_decision": "WATCHLIST", "urgency_score": 10, "evidence_gap_count": 1, "next_best_action": "Monitor."},
        ]
        result = render(queue)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(len(result["attention"]), 2)
        self.assertEqual(result["monitor_count"], 1)

    def test_invalid_action_fails_closed(self):
        result = render([{"director_action": "UNKNOWN"}])
        self.assertEqual(result["status"], "EVIDENCE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
