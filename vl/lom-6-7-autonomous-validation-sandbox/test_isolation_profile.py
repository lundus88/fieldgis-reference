import copy
import unittest

from isolation_profile import canonical_profile, validate_profile


class IsolationProfileTests(unittest.TestCase):
    def test_canonical_profile_ready(self):
        p = canonical_profile()
        self.assertEqual(validate_profile(p)["status"], "READY")
        self.assertEqual(p["workspace_mode"], "EPHEMERAL_COPY")
        self.assertFalse(p["host_workspace_direct_mount"])
        self.assertEqual(p["export_mode"], "ALLOWLIST_ONLY")
        self.assertEqual(p["network"], "DISABLED")
        self.assertEqual(p["credential_access"], "NONE")
        self.assertEqual(p["autonomous_ceiling"], "PREPARE_PR")
        self.assertEqual(p["production_authority"], "HUMAN_ONLY")

    def test_direct_host_mount_fails_closed(self):
        p = canonical_profile()
        p["host_workspace_direct_mount"] = True
        self.assertIn("host_workspace_direct_mount", validate_profile(p)["reason"])

    def test_unbounded_export_fails_closed(self):
        p = canonical_profile()
        p["export_mode"] = "COPY_ALL"
        self.assertIn("export_mode", validate_profile(p)["reason"])

    def test_network_fails_closed(self):
        p = canonical_profile()
        p["network"] = "ENABLED"
        self.assertIn("network", validate_profile(p)["reason"])

    def test_cleanup_required(self):
        p = canonical_profile()
        p["temporary_workspace_cleanup"] = "OPTIONAL"
        self.assertIn("temporary_workspace_cleanup", validate_profile(p)["reason"])

    def test_resource_ceiling_fails_closed(self):
        p = canonical_profile()
        p["max_memory_mb"] = 4096
        self.assertEqual(validate_profile(p)["reason"], "SANDBOX_MEMORY_LIMIT_INVALID")

    def test_digest_tamper_detected(self):
        p = canonical_profile()
        p["max_memory_mb"] = 1024
        self.assertEqual(validate_profile(p)["reason"], "SANDBOX_PROFILE_DIGEST_MISMATCH")


if __name__ == "__main__":
    unittest.main()
