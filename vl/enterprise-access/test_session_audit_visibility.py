import json
import unittest

from session_audit_visibility import SessionContext, build_audit_event, list_visible_sessions


class SessionAuditVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.session = SessionContext(
            session_id="sess-001",
            actor_id="user-a",
            workspace_id="ws-a",
            project_id="project-1",
            device_id="device-1",
            device_trust="managed",
            auth_method="oidc",
            issued_at="2026-09-06T10:00:00Z",
            expires_at="2026-09-06T18:00:00Z",
        )

    def test_public_session_never_exposes_raw_session_id(self):
        visible = self.session.public_view()
        self.assertNotIn("session_id", visible)
        self.assertRegex(visible["session_fingerprint"], r"^[0-9a-f]{64}$")

    def test_audit_event_contains_required_enterprise_dimensions(self):
        event = build_audit_event(
            session=self.session,
            action="project.read",
            policy_id="enterprise-access",
            policy_version="1",
            outcome="ALLOW",
            reason="ROLE_AND_ACP_MATCH",
            resource_scope="project:project-1",
            occurred_at="2026-09-06T10:05:00Z",
        )
        for key in (
            "actor_id", "workspace_id", "project_id", "action", "policy_id",
            "policy_version", "outcome", "session_fingerprint", "device_id",
            "device_trust", "auth_method", "resource_scope", "event_sha256"
        ):
            self.assertIn(key, event)
        self.assertEqual(event["schema"], "vl.enterprise-audit-event/1")

    def test_secret_metadata_is_redacted(self):
        event = build_audit_event(
            session=self.session,
            action="connector.invoke:example",
            policy_id="enterprise-access",
            policy_version="1",
            outcome="DENY",
            reason="CONNECTOR_SCOPE_DENIED",
            resource_scope="connector:example",
            occurred_at="2026-09-06T10:05:00Z",
            metadata={
                "token": "should-never-appear",
                "nested": {"api_key": "also-secret", "safe": "ok"},
            },
        )
        serialized = json.dumps(event)
        self.assertNotIn("should-never-appear", serialized)
        self.assertNotIn("also-secret", serialized)
        self.assertEqual(event["metadata"]["nested"]["safe"], "ok")

    def test_user_only_sees_own_session_without_auditor_capability(self):
        other = SessionContext(
            session_id="sess-002",
            actor_id="user-b",
            workspace_id="ws-a",
            project_id="project-2",
            device_id="device-2",
            device_trust="unknown",
            auth_method="password",
            issued_at="2026-09-06T10:00:00Z",
            expires_at="2026-09-06T18:00:00Z",
        )
        visible = list_visible_sessions(
            [self.session, other],
            viewer_actor_id="user-a",
            viewer_workspace_ids=["ws-a"],
            can_audit_workspace=False,
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["actor_id"], "user-a")

    def test_workspace_auditor_cannot_cross_workspace_boundary(self):
        same_ws = SessionContext(
            session_id="sess-003",
            actor_id="user-c",
            workspace_id="ws-a",
            project_id="project-3",
            device_id="device-3",
            device_trust="managed",
            auth_method="saml",
            issued_at="2026-09-06T10:00:00Z",
            expires_at="2026-09-06T18:00:00Z",
        )
        other_ws = SessionContext(
            session_id="sess-004",
            actor_id="user-d",
            workspace_id="ws-b",
            project_id="project-4",
            device_id="device-4",
            device_trust="managed",
            auth_method="saml",
            issued_at="2026-09-06T10:00:00Z",
            expires_at="2026-09-06T18:00:00Z",
        )
        visible = list_visible_sessions(
            [self.session, same_ws, other_ws],
            viewer_actor_id="auditor",
            viewer_workspace_ids=["ws-a"],
            can_audit_workspace=True,
        )
        self.assertEqual({item["workspace_id"] for item in visible}, {"ws-a"})
        self.assertEqual(len(visible), 2)

    def test_invalid_audit_outcome_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "INVALID_AUDIT_OUTCOME"):
            build_audit_event(
                session=self.session,
                action="project.read",
                policy_id="enterprise-access",
                policy_version="1",
                outcome="MAYBE",
                reason="UNKNOWN",
                resource_scope="project:project-1",
                occurred_at="2026-09-06T10:05:00Z",
            )


if __name__ == "__main__":
    unittest.main()
