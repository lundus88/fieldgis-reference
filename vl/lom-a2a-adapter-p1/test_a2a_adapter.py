import copy
import unittest

from a2a_adapter import (
    compile_agent_card_projection,
    project_message_metadata,
    validate_a2a_projection,
    validate_task_envelope,
)


def connector_registry():
    return {
        "schema": "lom.connector-registry/1",
        "registry_id": "lom-v1-readonly-connectors",
        "version": 3,
        "default_decision": "deny",
        "production_locked": True,
        "write_authority": False,
        "paid_action_authority": False,
        "ambient_credentials_allowed": False,
        "connectors": [
            {
                "id": "fixture-a2a-readonly",
                "version": "1.0.0",
                "status": "certified-fixture",
                "mode": "read-only",
                "allowed_operations": ["read"],
                "resource_scopes": ["fixture/a2a"],
                "external_runtime": False,
                "credentials_required": False,
                "protocol": "a2a",
                "protocol_version": "1.0",
                "network_access": "DISABLED",
                "agent_authority_trusted": False,
            }
        ],
    }


def action_registry():
    return {
        "schema": "lom.action-registry/1",
        "default_decision": "DENY",
        "production_locked": True,
        "actions": [
            {
                "action_id": "READ_ONLY_OBSERVATION",
                "capability_id": "cap.observe.readonly",
                "max_risk": "LOW",
                "reversible_required": True,
                "non_production_only": True,
            }
        ],
        "human_only_actions": ["PRODUCTION_RELEASE"],
    }


def binding():
    return [{
        "connector_id": "fixture-a2a-readonly",
        "a2a_skill_id": "catalog.lookup",
        "action_id": "READ_ONLY_OBSERVATION",
        "capability_id": "cap.observe.readonly",
        "resource_scope": "fixture/a2a",
    }]


def card():
    return {
        "name": "Fixture Agent",
        "description": "Read-only fixture agent.",
        "version": "1.0.0",
        "supportedInterfaces": [{
            "protocolBinding": "JSONRPC",
            "url": "https://example.invalid/a2a",
            "protocolVersion": "1.0",
        }],
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["application/json"],
        "securitySchemes": {},
        "security": [],
        "skills": [
            {
                "id": "catalog.lookup",
                "name": "Catalog Lookup",
                "description": "Lookup fixture catalog metadata.",
                "tags": ["read-only"],
            },
            {
                "id": "agent.claimed.safe",
                "name": "Claimed Safe",
                "description": "Unbound skill advertised by external agent.",
                "tags": ["read-only"],
            },
        ],
    }


class A2AAdapterTests(unittest.TestCase):
    def test_local_binding_not_agent_claim_controls_skill_eligibility(self):
        out = compile_agent_card_projection(
            connector_id="fixture-a2a-readonly",
            agent_card=card(),
            connector_registry=connector_registry(),
            action_registry=action_registry(),
            local_skill_bindings=binding(),
        )
        self.assertEqual(out["status"], "READY")
        self.assertEqual(len(out["eligible_skills"]), 1)
        self.assertEqual(out["eligible_skills"][0]["id"], "catalog.lookup")
        self.assertFalse(out["eligible_skills"][0]["delegation_enabled"])
        self.assertFalse(out["eligible_skills"][0]["execution_enabled"])
        self.assertEqual(len(out["denied_skills"]), 1)
        self.assertEqual(out["denied_skills"][0]["reason"], "UNBOUND_A2A_SKILL")
        self.assertFalse(out["agent_authority_trusted"])
        self.assertEqual(validate_a2a_projection(out)["status"], "READY")

    def test_security_requirement_fails_closed(self):
        c = card()
        c["securitySchemes"] = {"oauth2": {"type": "oauth2"}}
        out = compile_agent_card_projection(
            connector_id="fixture-a2a-readonly",
            agent_card=c,
            connector_registry=connector_registry(),
            action_registry=action_registry(),
            local_skill_bindings=binding(),
        )
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "A2A_SECURITY_REQUIREMENTS_FORBIDDEN_P1")

    def test_protocol_version_mismatch_fails_closed(self):
        c = card()
        c["supportedInterfaces"][0]["protocolVersion"] = "0.3"
        out = compile_agent_card_projection(
            connector_id="fixture-a2a-readonly",
            agent_card=c,
            connector_registry=connector_registry(),
            action_registry=action_registry(),
            local_skill_bindings=binding(),
        )
        self.assertEqual(out["reason"], "A2A_INTERFACE_VERSION_MISMATCH")

    def test_message_content_is_not_forwarded(self):
        out = project_message_metadata({
            "messageId": "m1",
            "role": "ROLE_AGENT",
            "parts": [{"text": "sensitive content"}],
        })
        self.assertEqual(out["status"], "READY")
        self.assertEqual(out["part_types"], ["text"])
        self.assertFalse(out["content_forwarded"])
        self.assertEqual(out["message_authority"], "NON_AUTHORITATIVE_COMMUNICATION")

    def test_input_required_is_human_gate(self):
        out = validate_task_envelope({
            "id": "task-1",
            "status": {"state": "TASK_STATE_INPUT_REQUIRED"},
        })
        self.assertEqual(out["decision"], "HUMAN_GATE")
        self.assertEqual(out["reason"], "A2A_INPUT_REQUIRED")
        self.assertEqual(out["auto_response"], "FORBIDDEN")

    def test_auth_required_is_human_gate_and_credentials_forbidden(self):
        out = validate_task_envelope({
            "id": "task-2",
            "status": {"state": "TASK_STATE_AUTH_REQUIRED"},
        })
        self.assertEqual(out["decision"], "HUMAN_GATE")
        self.assertEqual(out["reason"], "A2A_AUTH_REQUIRED")
        self.assertEqual(out["credential_forwarding"], "FORBIDDEN")

    def test_completed_task_requires_artifact(self):
        out = validate_task_envelope({
            "id": "task-3",
            "status": {"state": "TASK_STATE_COMPLETED"},
            "artifacts": [],
        })
        self.assertEqual(out["decision"], "HOLD")
        self.assertEqual(out["reason"], "A2A_COMPLETED_TASK_ARTIFACT_REQUIRED")

    def test_completed_artifact_is_metadata_only_until_lom_verification(self):
        out = validate_task_envelope({
            "id": "task-4",
            "contextId": "ctx-1",
            "status": {"state": "TASK_STATE_COMPLETED"},
            "artifacts": [{
                "artifactId": "a1",
                "name": "result",
                "parts": [{"data": {"answer": 42}}],
            }],
            "history": [{
                "messageId": "m1",
                "role": "ROLE_AGENT",
                "parts": [{"text": "done"}],
            }],
        })
        self.assertEqual(out["decision"], "ALLOW_METADATA_ONLY")
        self.assertTrue(out["artifact_requires_lom_verification"])
        self.assertFalse(out["artifact_content_forwarded"])
        self.assertFalse(out["message_content_forwarded"])

    def test_tampered_projection_fails_closed(self):
        out = compile_agent_card_projection(
            connector_id="fixture-a2a-readonly",
            agent_card=card(),
            connector_registry=connector_registry(),
            action_registry=action_registry(),
            local_skill_bindings=binding(),
        )
        tampered = copy.deepcopy(out)
        tampered["external_delegation"] = "ENABLED"
        self.assertEqual(
            validate_a2a_projection(tampered)["reason"],
            "A2A_INVARIANT_WEAKENED:external_delegation",
        )


if __name__ == "__main__":
    unittest.main()
