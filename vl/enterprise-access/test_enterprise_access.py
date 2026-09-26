import json
import unittest
from pathlib import Path

from authorize_workspace_action import decide, validate_policy


HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "enterprise-access-policy.json").read_text())


def snapshot(role="builder", connector_scopes=None, data_classes=None):
    return {
        "workspace_memberships": [
            {"workspace_id": "ws-a", "user_id": "user-a", "role": role, "status": "active"}
        ],
        "project_memberships": [
            {
                "workspace_id": "ws-a",
                "project_id": "project-a",
                "user_id": "user-a",
                "role": role,
                "status": "active",
                "connector_scopes": connector_scopes or [],
                "data_classifications": data_classes or ["public", "internal"],
                "retention_profile": "standard",
                "retention_profiles": ["standard"],
            }
        ],
    }


def request(capability="factory.enqueue", **overrides):
    base = {
        "user_id": "user-a",
        "principal_type": "human",
        "workspace_id": "ws-a",
        "project_id": "project-a",
        "capability": capability,
        "acp_capabilities": [capability],
        "data_classification": "internal",
        "retention_profile": "standard",
    }
    base.update(overrides)
    return base


class EnterpriseAccessTests(unittest.TestCase):
    def test_policy_is_default_deny_and_roles_cannot_grant_production(self):
        validate_policy(POLICY)
        self.assertEqual(POLICY["default_decision"], "deny")
        for caps in POLICY["roles"].values():
            self.assertNotIn("production.approve", caps)
            self.assertNotIn("production.promote", caps)

    def test_builder_requires_both_membership_and_acp_grant(self):
        allowed = decide(POLICY, snapshot("builder"), request("factory.enqueue"))
        self.assertEqual(allowed["decision"], "allow")
        denied = decide(POLICY, snapshot("builder"), request("factory.enqueue", acp_capabilities=[]))
        self.assertEqual(denied["reason_code"], "DENY_ACP_CAPABILITY_NOT_GRANTED")

    def test_cross_project_scope_is_denied(self):
        result = decide(POLICY, snapshot("builder"), request("factory.enqueue", project_id="project-b"))
        self.assertEqual(result["reason_code"], "DENY_PROJECT_MEMBERSHIP")

    def test_viewer_cannot_enqueue_even_with_forged_acp_capability(self):
        result = decide(POLICY, snapshot("viewer"), request("factory.enqueue"))
        self.assertEqual(result["reason_code"], "DENY_ROLE_CAPABILITY")

    def test_restricted_data_requires_explicit_project_classification(self):
        denied = decide(POLICY, snapshot("builder"), request("factory.enqueue", data_classification="restricted"))
        self.assertEqual(denied["reason_code"], "DENY_RESTRICTED_DATA_SCOPE")
        allowed = decide(POLICY, snapshot("builder", data_classes=["internal", "restricted"]), request("factory.enqueue", data_classification="restricted"))
        self.assertEqual(allowed["decision"], "allow")

    def test_connector_requires_role_acp_and_exact_project_scope(self):
        cap = "connector.invoke:github"
        allowed = decide(POLICY, snapshot("builder", connector_scopes=["github"]), request(cap, connector="github"))
        self.assertEqual(allowed["decision"], "allow")
        denied = decide(POLICY, snapshot("builder", connector_scopes=["github"]), request("connector.invoke:gmail", connector="gmail"))
        self.assertEqual(denied["reason_code"], "DENY_CONNECTOR_SCOPE")

    def test_ambient_connector_credentials_are_denied(self):
        cap = "connector.invoke:github"
        result = decide(POLICY, snapshot("builder", connector_scopes=["github"]), request(cap, connector="github", ambient_credentials=True))
        self.assertEqual(result["reason_code"], "DENY_AMBIENT_CREDENTIALS")

    def test_high_impact_connector_requires_human_action_approval(self):
        cap = "connector.invoke:github"
        result = decide(POLICY, snapshot("builder", connector_scopes=["github"]), request(cap, connector="github", paid_or_high_impact=True))
        self.assertEqual(result["decision"], "require_human_approval")
        self.assertEqual(result["reason_code"], "REQUIRE_HUMAN_HIGH_IMPACT_CONNECTOR_APPROVAL")

    def test_production_approval_is_explicit_human_and_separated_from_builder(self):
        cap = "production.approve"
        agent = decide(POLICY, snapshot("reviewer"), request(cap, principal_type="agent", explicit_production_approval_grant=True))
        self.assertEqual(agent["reason_code"], "DENY_PRODUCTION_APPROVAL_NON_HUMAN")
        no_grant = decide(POLICY, snapshot("reviewer"), request(cap))
        self.assertEqual(no_grant["reason_code"], "DENY_EXPLICIT_APPROVAL_GRANT_REQUIRED")
        conflict = decide(POLICY, snapshot("reviewer"), request(cap, explicit_production_approval_grant=True, built_project_ids=["project-a"]))
        self.assertEqual(conflict["reason_code"], "DENY_APPROVER_BUILDER_CONFLICT")
        allowed = decide(POLICY, snapshot("reviewer"), request(cap, explicit_production_approval_grant=True, built_project_ids=[]))
        self.assertEqual(allowed["decision"], "allow")

    def test_audit_decision_contains_no_secret_value(self):
        result = decide(POLICY, snapshot("builder"), request("factory.enqueue", secret="DO_NOT_RECORD_ME"))
        encoded = json.dumps(result)
        self.assertNotIn("DO_NOT_RECORD_ME", encoded)
        self.assertFalse(result["secret_values_recorded"])
        self.assertFalse(result["direct_execution_authority"])


if __name__ == "__main__":
    unittest.main()
