import json
import unittest
from pathlib import Path

from enterprise_authorization_adapter import authorize_with_audit
from session_audit_visibility import SessionContext


HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "enterprise-access-policy.json").read_text())


class EnterpriseAuthorizationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "workspace_memberships": [
                {"workspace_id": "w1", "user_id": "u1", "status": "active", "role": "builder"}
            ],
            "project_memberships": [
                {
                    "workspace_id": "w1",
                    "project_id": "p1",
                    "user_id": "u1",
                    "status": "active",
                    "role": "builder",
                    "data_classifications": ["internal", "restricted"],
                    "retention_profiles": ["standard", "regulated"],
                    "connector_scopes": ["github"],
                }
            ],
        }
        self.request = {
            "user_id": "u1",
            "principal_type": "human",
            "workspace_id": "w1",
            "project_id": "p1",
            "capability": "project.read",
            "acp_capabilities": ["project.read"],
            "data_classification": "internal",
            "retention_profile": "standard",
        }
        self.parent = {
            "capabilities": ["project.read", "artifact.read"],
            "classifications": ["public", "internal", "restricted"],
            "retention_profiles": ["standard", "regulated"],
            "restricted_projects": ["p1"],
        }
        self.child = {
            "capabilities": ["project.read"],
            "classifications": ["internal", "restricted"],
            "retention_profiles": ["standard", "regulated"],
            "restricted_projects": ["p1"],
        }
        self.session = SessionContext(
            session_id="raw-session-secret",
            actor_id="u1",
            workspace_id="w1",
            project_id="p1",
            device_id="device-1",
            device_trust="managed",
            auth_method="oidc",
            issued_at="2026-09-06T00:00:00Z",
            expires_at="2026-09-06T12:00:00Z",
        )

    def call(self, **overrides):
        values = {
            "enterprise_policy": POLICY,
            "membership_snapshot": self.snapshot,
            "request": self.request,
            "parent_data_policy": self.parent,
            "child_data_policy": self.child,
            "session": self.session,
            "occurred_at": "2026-09-06T01:00:00Z",
        }
        values.update(overrides)
        return authorize_with_audit(**values)

    def test_allow_requires_all_layers(self):
        result = self.call()
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["audit_event"]["outcome"], "ALLOW")
        self.assertFalse(result["direct_execution_authority"])
        self.assertFalse(result["production_authority"])
        self.assertNotIn("raw-session-secret", json.dumps(result))

    def test_acp_denial_stays_denied(self):
        request = dict(self.request, acp_capabilities=[])
        result = self.call(request=request)
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reason"], "DENY_ACP_CAPABILITY_NOT_GRANTED")
        self.assertEqual(result["audit_event"]["outcome"], "DENY")

    def test_inherited_policy_widening_denied(self):
        child = dict(self.child, capabilities=["project.read", "production.approve"])
        result = self.call(child_data_policy=child)
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reason"], "DENY_POLICY_INHERITANCE_INVALID")

    def test_restricted_scope_escape_denied(self):
        request = dict(self.request, data_classification="restricted")
        child = dict(self.child, restricted_projects=[])
        result = self.call(request=request, child_data_policy=child)
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reason"], "DENY_DATA_POLICY_RESTRICTED_PROJECT_GRANT_REQUIRED")

    def test_session_actor_mismatch_denied_before_authorization(self):
        session = SessionContext(
            session_id="s2",
            actor_id="attacker",
            workspace_id="w1",
            project_id="p1",
            device_id="device-x",
            device_trust="unknown",
            auth_method="local",
            issued_at="2026-09-06T00:00:00Z",
            expires_at="2026-09-06T12:00:00Z",
        )
        result = self.call(session=session)
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reason"], "DENY_SESSION_ACTOR_MISMATCH")

    def test_high_impact_connector_hold_is_audited(self):
        request = dict(
            self.request,
            capability="connector.invoke:github",
            connector="github",
            acp_capabilities=["connector.invoke:github"],
            paid_or_high_impact=True,
            human_action_approval=False,
        )
        parent = dict(self.parent, capabilities=["project.read", "connector.invoke:github"])
        child = dict(self.child, capabilities=["connector.invoke:github"])
        result = self.call(request=request, parent_data_policy=parent, child_data_policy=child)
        self.assertEqual(result["decision"], "require_human_approval")
        self.assertEqual(result["audit_event"]["outcome"], "HOLD")


if __name__ == "__main__":
    unittest.main()
