import unittest
from pathlib import Path

from vl_production_adapter import (
    adapter_for, all_checks_pass, callback_is_current, configuration_status,
    require_previous_certified, verify_http_contract, verify_sha256,
)


class Response:
    status = 200
    def __init__(self, body: bytes): self.body = body
    def read(self): return self.body


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

    def test_provider_accepts_but_health_fails(self):
        checks = verify_http_contract(
            "https://controlled.invalid/health", expected_json={"ok": True},
            opener=lambda *_args, **_kwargs: Response(b'{"ok":false}'),
        )
        self.assertFalse(all_checks_pass(checks))
        self.assertEqual("FAIL", next(x for x in checks if x["check_key"] == "response.ok")["status"])

    def test_health_contract_passes_only_with_all_checks(self):
        checks = verify_http_contract(
            "https://controlled.invalid/health", expected_json={"ok": True, "schema": "vl.health/1"},
            opener=lambda *_args, **_kwargs: Response(b'{"ok":true,"schema":"vl.health/1"}'),
        )
        self.assertTrue(all_checks_pass(checks))

    def test_rollback_requires_previous_certified_provider_release(self):
        with self.assertRaisesRegex(ValueError, "previous certified"):
            require_previous_certified([{"id": "old", "status": "deployed", "certificate": {}}], "new")

    def test_rollback_selects_latest_known_good(self):
        deployments = [
            {"id":"old","status":"deployed","deployed_at":"2026-01-01","artifact_sha256":"a","provider_deployment_id":"p1","certificate":{"technical_validation":"PASS"}},
            {"id":"latest","status":"deployed","deployed_at":"2026-02-01","artifact_sha256":"b","provider_deployment_id":"p2","certificate":{"technical_validation":"PASS"}},
        ]
        self.assertEqual("latest", require_previous_certified(deployments, "new")["id"])


if __name__ == "__main__":
    unittest.main()
