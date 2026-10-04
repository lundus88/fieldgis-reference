import copy
import unittest

from mcp_adapter import MCP_TASKS_EXTENSION, compile_mcp_discovery_projection, validate_mcp_projection, validate_task_handle


def connectors():
    return {
        "schema":"lom.connector-registry/1","registry_id":"x","version":2,
        "default_decision":"deny","production_locked":True,"write_authority":False,
        "paid_action_authority":False,"ambient_credentials_allowed":False,
        "connectors":[{
            "id":"fixture-mcp-readonly","version":"1.0.0","status":"certified-fixture",
            "mode":"read-only","allowed_operations":["read"],"resource_scopes":["fixture/mcp"],
            "external_runtime":False,"credentials_required":False,"protocol":"mcp",
            "protocol_version":"2026-07-28","network_access":"DISABLED",
            "server_authority_trusted":False
        }]
    }


def actions():
    return {
        "schema":"lom.action-registry/1","default_decision":"DENY","production_locked":True,
        "actions":[{
            "action_id":"READ_ONLY_OBSERVATION","capability_id":"cap.observe.readonly",
            "max_risk":"LOW","reversible_required":True,"non_production_only":True
        }],
        "human_only_actions":["PRODUCTION_RELEASE"]
    }


def binding():
    return [{
        "connector_id":"fixture-mcp-readonly","mcp_tool_name":"lookup_fixture",
        "action_id":"READ_ONLY_OBSERVATION","capability_id":"cap.observe.readonly",
        "resource_scope":"fixture/mcp"
    }]


def discovery():
    return {
        "protocol_version":"2026-07-28",
        "server":{"name":"fixture","version":"1.0.0"},
        "capabilities":{"tools":True,"resources":True,"prompts":True},
        "extensions":[MCP_TASKS_EXTENSION],
        "tools":[
            {"name":"lookup_fixture","inputSchema":{"type":"object","properties":{}},"annotations":{"readOnlyHint":False}},
            {"name":"server_claimed_readonly","inputSchema":{"type":"object","properties":{}},"annotations":{"readOnlyHint":True}}
        ],
        "resources":[{"uri":"fixture://catalog","name":"catalog"}],
        "prompts":[{"name":"helper"}]
    }


class MCPAdapterTests(unittest.TestCase):
    def test_local_binding_controls_eligibility(self):
        out=compile_mcp_discovery_projection(
            connector_id="fixture-mcp-readonly",discovery=discovery(),
            connector_registry=connectors(),action_registry=actions(),local_bindings=binding())
        self.assertEqual(out["status"],"READY")
        self.assertEqual(len(out["eligible_tools"]),1)
        self.assertEqual(out["eligible_tools"][0]["authority_source"],"LOM_LOCAL_BINDING")
        self.assertFalse(out["eligible_tools"][0]["execution_enabled"])
        self.assertEqual(len(out["denied_tools"]),1)
        self.assertEqual(out["denied_tools"][0]["reason"],"UNBOUND_MCP_TOOL")
        self.assertEqual(validate_mcp_projection(out)["status"],"READY")

    def test_server_hint_never_grants_authority(self):
        out=compile_mcp_discovery_projection(
            connector_id="fixture-mcp-readonly",discovery=discovery(),
            connector_registry=connectors(),action_registry=actions(),local_bindings=[])
        self.assertEqual(len(out["eligible_tools"]),0)
        self.assertEqual(len(out["denied_tools"]),2)

    def test_protocol_mismatch_holds(self):
        d=discovery(); d["protocol_version"]="2025-11-25"
        out=compile_mcp_discovery_projection(
            connector_id="fixture-mcp-readonly",discovery=d,
            connector_registry=connectors(),action_registry=actions(),local_bindings=binding())
        self.assertEqual(out["reason"],"MCP_DISCOVERY_PROTOCOL_VERSION_MISMATCH")

    def test_live_network_holds(self):
        c=connectors(); c["connectors"][0]["network_access"]="ENABLED"
        out=compile_mcp_discovery_projection(
            connector_id="fixture-mcp-readonly",discovery=discovery(),
            connector_registry=c,action_registry=actions(),local_bindings=binding())
        self.assertEqual(out["reason"],"MCP_NETWORK_ACCESS_FORBIDDEN_P1")

    def test_binding_cannot_widen_action(self):
        b=binding(); b[0]["action_id"]="PRODUCTION_RELEASE"
        out=compile_mcp_discovery_projection(
            connector_id="fixture-mcp-readonly",discovery=discovery(),
            connector_registry=connectors(),action_registry=actions(),local_bindings=b)
        self.assertEqual(out["reason"],"MCP_LOCAL_BINDING_ACTION_FORBIDDEN")

    def test_task_metadata_validation(self):
        task={"taskId":"786512e2-9e0d-44bd-8f29-789f320fe840","status":"working",
              "createdAt":"2026-10-04T00:00:00Z","lastUpdatedAt":"2026-10-04T00:00:01Z",
              "ttlMs":60000,"pollIntervalMs":5000}
        out=validate_task_handle(task,tasks_extension_declared=True)
        self.assertEqual(out["decision"],"ALLOW_METADATA_ONLY")
        self.assertEqual(out["network_action"],"DISABLED")

    def test_input_required_human_gates(self):
        task={"taskId":"786512e2-9e0d-44bd-8f29-789f320fe840","status":"input_required",
              "createdAt":"2026-10-04T00:00:00Z","lastUpdatedAt":"2026-10-04T00:00:01Z",
              "ttlMs":60000,"inputRequests":{"r1":{"method":"elicitation/create"}}}
        out=validate_task_handle(task,tasks_extension_declared=True)
        self.assertEqual(out["decision"],"HUMAN_GATE")
        self.assertEqual(out["auto_response"],"FORBIDDEN")

    def test_completed_task_requires_result(self):
        task={"taskId":"786512e2-9e0d-44bd-8f29-789f320fe840","status":"completed",
              "createdAt":"2026-10-04T00:00:00Z","lastUpdatedAt":"2026-10-04T00:00:01Z","ttlMs":None}
        out=validate_task_handle(task,tasks_extension_declared=True)
        self.assertEqual(out["reason"],"MCP_COMPLETED_TASK_RESULT_REQUIRED")

    def test_projection_tamper_detected(self):
        out=compile_mcp_discovery_projection(
            connector_id="fixture-mcp-readonly",discovery=discovery(),
            connector_registry=connectors(),action_registry=actions(),local_bindings=binding())
        t=copy.deepcopy(out); t["network_access"]="ENABLED"
        self.assertEqual(validate_mcp_projection(t)["reason"],"MCP_LIVE_NETWORK_FORBIDDEN_P1")


if __name__=="__main__":
    unittest.main()
