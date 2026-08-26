import unittest
from pathlib import Path

from vl_production_adapter import adapter_for, callback_is_current, configuration_status, verify_sha256


class ProductionAdapterTests(unittest.TestCase):
    def test_unknown_adapter_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UNCONFIGURED"):
            adapter_for("unknown-v1")

    def test_vercel_missing_credentials_is_blocked(self):
        status, missing = configuration_status("web-react-v1", {})
        self.assertEqual("BLOCKED/UNCONFIGURED", status)
        self.assertEqual({"VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"}, set(missing))

    def test_mobile_requires_no_external_credentials(self):
        self.assertEqual(("CONFIGURED", []), configuration_status("mobile-flutter-v1", {}))

    def test_hash_mismatch_fails(self):
        path = Path(__file__)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            verify_sha256(path, "0" * 64)

    def test_stale_callback_rejected(self):
        job = {"state": "leased", "lease_token": "current"}
        self.assertTrue(callback_is_current(job, "current"))
        self.assertFalse(callback_is_current(job, "stale"))
        self.assertFalse(callback_is_current({**job, "state": "succeeded"}, "current"))


if __name__ == "__main__":
    unittest.main()
