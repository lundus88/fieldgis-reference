import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_queue import build_queue


class QueueTests(unittest.TestCase):
    def test_state_order_is_preserved(self):
        items = [
            {"decision": "HOLD", "deadline_urgency": 100, "evidence_gap_count": 1},
            {"decision": "CONTINUE", "deadline_urgency": 0, "evidence_gap_count": 0},
        ]
        queue = build_queue(items)
        self.assertEqual(queue[0]["pursuit_decision"], "CONTINUE")
        self.assertEqual(queue[1]["pursuit_decision"], "HOLD")

    def test_invalid_state_fails_closed(self):
        queue = build_queue([{"decision": "INVALID", "deadline_urgency": 10, "evidence_gap_count": 2}])
        self.assertEqual(queue[0]["pursuit_decision"], "HOLD")

    def test_watchlist_action(self):
        queue = build_queue([{"decision": "WATCHLIST", "deadline_urgency": 20, "evidence_gap_count": 0}])
        self.assertEqual(queue[0]["director_action"], "MONITOR")


if __name__ == "__main__":
    unittest.main()
