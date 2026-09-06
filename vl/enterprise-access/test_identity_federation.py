import unittest

from identity_federation import normalize_identity_assertion, plan_scim_change


class IdentityFederationTests(unittest.TestCase):
    def test_oidc_identity_normalizes_deterministically(self):
        assertion = {
            "protocol": "OIDC",
            "issuer": "https://idp.example.gov",
            "subject": "employee-123",
            "workspace_id": "agency-a",
            "email": "employee@example.gov",
            "groups": ["surveyors", "reviewers", "surveyors"],
            "authenticated_at": "2026-09-06T12:00:00Z",
        }
        first = normalize_identity_assertion(assertion)
        second = normalize_identity_assertion(assertion)
        self.assertEqual(first, second)
        self.assertEqual(first["protocol"], "oidc")
        self.assertEqual(first["groups"], ["reviewers", "surveyors"])
        self.assertRegex(first["identity_fingerprint"], r"^[0-9a-f]{64}$")

    def test_unknown_protocol_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_FEDERATION_PROTOCOL"):
            normalize_identity_assertion({
                "protocol": "legacy-custom",
                "issuer": "issuer",
                "subject": "subject",
                "workspace_id": "ws",
                "authenticated_at": "2026-09-06T12:00:00Z",
            })

    def test_scim_is_dry_run_only(self):
        plan = plan_scim_change(
            operation="USER_UPDATE",
            workspace_id="agency-a",
            external_subject="employee-123",
            target_roles=["builder", "reviewer"],
            allowed_roles=["builder", "reviewer", "viewer"],
            dry_run=True,
        )
        self.assertEqual(plan["mode"], "DRY_RUN_ONLY")
        self.assertFalse(plan["live_provisioning"])
        self.assertFalse(plan["production_authority"])
        self.assertRegex(plan["external_subject_fingerprint"], r"^[0-9a-f]{64}$")

    def test_live_scim_provisioning_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "SCIM_LIVE_PROVISIONING_NOT_ENABLED"):
            plan_scim_change(
                operation="USER_CREATE",
                workspace_id="agency-a",
                external_subject="employee-123",
                target_roles=["viewer"],
                allowed_roles=["viewer"],
                dry_run=False,
            )

    def test_scim_cannot_assign_role_outside_workspace_policy(self):
        with self.assertRaisesRegex(ValueError, "SCIM_ROLE_SCOPE_DENIED"):
            plan_scim_change(
                operation="GROUP_MEMBERSHIP_SYNC",
                workspace_id="agency-a",
                external_subject="employee-123",
                target_roles=["owner"],
                allowed_roles=["builder", "reviewer", "viewer"],
                dry_run=True,
            )


if __name__ == "__main__":
    unittest.main()
