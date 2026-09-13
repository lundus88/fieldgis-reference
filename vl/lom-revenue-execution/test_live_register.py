import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parent


class LiveRegisterTests(unittest.TestCase):
    def test_register_is_fail_closed(self):
        data = json.loads((ROOT / "live-opportunity-register.json").read_text())
        self.assertTrue(data["entries"])
        for entry in data["entries"]:
            self.assertIn(entry["status"], {"HOLD", "WATCHLIST"})
            self.assertTrue(entry["evidence"])
            self.assertTrue(entry["next_action"])


if __name__ == "__main__":
    unittest.main()
