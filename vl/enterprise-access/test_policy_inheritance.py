import unittest

from policy_inheritance import PolicyError, authorize_data_access, derive_effective_policy


PARENT = {
    "capabilities": ["project.read", "artifact.read", "audit.read"],
    "classifications": ["public", "internal", "confidential", "restricted"],
    "retention_profiles": ["standard", "short", "regulated"],
    "restricted_projects": ["project-a", "project-b"],
}


class PolicyInheritanceTests(unittest.TestCase):
    def test_child_can_narrow_parent(self):
        effective = derive_effective_policy(PARENT, {
            "capabilities": ["project.read", "artifact.read"],
            "classifications": ["public", "internal"],
            "retention_profiles": ["short"],
            "restricted_projects": [],
        })
        self.assertEqual(effective.capabilities, frozenset({"project.read", "artifact.read"}))

    def test_child_cannot_widen_capability(self):
        with self.assertRaisesRegex(PolicyError, "widens"):
            derive_effective_policy(PARENT, {
                "capabilities": ["project.read", "production.approve"],
                "classifications": ["public"],
                "retention_profiles": ["short"],
                "restricted_projects": [],
            })

    def test_child_cannot_widen_restricted_project_scope(self):
        with self.assertRaisesRegex(PolicyError, "widens"):
            derive_effective_policy(PARENT, {
                "capabilities": ["project.read"],
                "classifications": ["restricted"],
                "retention_profiles": ["regulated"],
                "restricted_projects": ["project-c"],
            })

    def test_unknown_classification_denied(self):
        effective = derive_effective_policy(PARENT, {
            "capabilities": ["project.read"],
            "classifications": ["public"],
            "retention_profiles": ["standard"],
            "restricted_projects": [],
        })
        result = authorize_data_access(
            effective,
            project_id="project-a",
            classification="secret-plus",
            retention_profile="standard",
            capability="project.read",
        )
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reason"], "UNKNOWN_CLASSIFICATION")

    def test_unknown_retention_denied(self):
        effective = derive_effective_policy(PARENT, {
            "capabilities": ["project.read"],
            "classifications": ["public"],
            "retention_profiles": ["standard"],
            "restricted_projects": [],
        })
        result = authorize_data_access(
            effective,
            project_id="project-a",
            classification="public",
            retention_profile="forever",
            capability="project.read",
        )
        self.assertEqual(result["reason"], "UNKNOWN_RETENTION_PROFILE")

    def test_restricted_requires_exact_project_grant(self):
        effective = derive_effective_policy(PARENT, {
            "capabilities": ["project.read"],
            "classifications": ["restricted"],
            "retention_profiles": ["regulated"],
            "restricted_projects": ["project-a"],
        })
        denied = authorize_data_access(
            effective,
            project_id="project-b",
            classification="restricted",
            retention_profile="regulated",
            capability="project.read",
        )
        self.assertEqual(denied["reason"], "RESTRICTED_PROJECT_GRANT_REQUIRED")
        allowed = authorize_data_access(
            effective,
            project_id="project-a",
            classification="restricted",
            retention_profile="regulated",
            capability="project.read",
        )
        self.assertEqual(allowed["decision"], "allow")

    def test_missing_effective_capability_denied(self):
        effective = derive_effective_policy(PARENT, {
            "capabilities": ["artifact.read"],
            "classifications": ["public"],
            "retention_profiles": ["standard"],
            "restricted_projects": [],
        })
        result = authorize_data_access(
            effective,
            project_id="project-a",
            classification="public",
            retention_profile="standard",
            capability="audit.read",
        )
        self.assertEqual(result["reason"], "CAPABILITY_NOT_EFFECTIVE")


if __name__ == "__main__":
    unittest.main()
