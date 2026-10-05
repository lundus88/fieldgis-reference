import unittest

from openai_responses_adapter import (
    OPENAI_RESPONSES_ENDPOINT,
    authorize_nonprod_live_call,
    normalize_openai_response,
    prepare_openai_request,
)


def route():
    return {
        "provider": "openai",
        "model_id": "openai/model-approved-v1",
        "certified": True,
        "production_locked": True,
        "training": "disabled",
        "retention": "none",
        "decision_sha256": "a" * 64,
    }


def schema():
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["title", "summary"],
        "additionalProperties": False,
    }


def envelope(**kw):
    data = {
        "request_id": "req-001",
        "job_id": "YT-SHADOW-001",
        "content_id": "LOM-YT-001",
        "capability": "youtube.script.generate",
        "input_text": "Draft an original script from verified source notes.",
        "route_binding": route(),
        "output_schema": schema(),
        "environment": "development",
        "max_output_tokens": 2000,
    }
    data.update(kw)
    return data


class OpenAIResponsesAdapterP0Tests(unittest.TestCase):
    def test_prepare_request_uses_responses_api_and_strict_structured_output(self):
        r = prepare_openai_request(envelope())
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["http"]["endpoint"], OPENAI_RESPONSES_ENDPOINT)
        self.assertEqual(r["http"]["body"]["store"], False)
        self.assertEqual(r["http"]["body"]["tools"], [])
        self.assertEqual(r["http"]["body"]["text"]["format"]["type"], "json_schema")
        self.assertEqual(r["http"]["body"]["text"]["format"]["strict"], True)
        self.assertEqual(r["http"]["auth_mode"], "BROKER_INJECTED_BEARER")
        self.assertNotIn("Authorization", r["http"])

    def test_secret_material_is_rejected(self):
        r = prepare_openai_request(envelope(api_key="sk-test-should-never-be-here"))
        self.assertEqual(r["reason"], "SECRET_MATERIAL_FORBIDDEN")

    def test_only_openai_certified_nonprod_route_allowed(self):
        bad = route()
        bad["provider"] = "other"
        self.assertEqual(prepare_openai_request(envelope(route_binding=bad))["reason"], "OPENAI_ROUTE_REQUIRED")
        bad = route()
        bad["certified"] = False
        self.assertEqual(prepare_openai_request(envelope(route_binding=bad))["reason"], "CERTIFIED_ROUTE_REQUIRED")
        bad = route()
        bad["production_locked"] = False
        self.assertEqual(prepare_openai_request(envelope(route_binding=bad))["reason"], "PRODUCTION_LOCK_REQUIRED")

    def test_privacy_and_environment_fail_closed(self):
        bad = route()
        bad["retention"] = "30_days"
        self.assertEqual(prepare_openai_request(envelope(route_binding=bad))["reason"], "PRIVACY_POLICY_MISMATCH")
        self.assertEqual(prepare_openai_request(envelope(environment="production"))["reason"], "NONPRODUCTION_ENVIRONMENT_REQUIRED")

    def test_capability_and_token_bound_enforced(self):
        self.assertEqual(prepare_openai_request(envelope(capability="youtube.upload.private"))["reason"], "CAPABILITY_NOT_ALLOWED")
        self.assertEqual(prepare_openai_request(envelope(max_output_tokens=8001))["reason"], "OUTPUT_TOKEN_BOUND_INVALID")

    def test_strict_schema_requires_all_properties_required(self):
        bad = schema()
        bad["required"] = ["title"]
        self.assertEqual(prepare_openai_request(envelope(output_schema=bad))["reason"], "STRICT_OUTPUT_SCHEMA_REQUIRED")

    def test_live_call_requires_broker_and_independently_verified_human_approval(self):
        p = prepare_openai_request(envelope())
        broker = {
            "broker_id": "lom-openai-nonprod",
            "environment": "development",
            "secret_injected_server_side": True,
            "worker_secret_access": False,
            "production_locked": True,
        }
        approval = {
            "status": "VERIFIED",
            "principal_type": "human",
            "request_digest": p["request_digest"],
            "evidence_ref": "approval:owner:yt-shadow-001",
        }
        self.assertEqual(authorize_nonprod_live_call(p, broker, approval)["decision"], "ALLOW")
        bad = dict(approval)
        bad["request_digest"] = "b" * 64
        self.assertEqual(authorize_nonprod_live_call(p, broker, bad)["reason"], "APPROVAL_DIGEST_MISMATCH")
        bad_broker = dict(broker)
        bad_broker["worker_secret_access"] = True
        self.assertEqual(authorize_nonprod_live_call(p, bad_broker, approval)["reason"], "WORKER_SECRET_ACCESS_FORBIDDEN")

    def test_normalize_verified_structured_response(self):
        p = prepare_openai_request(envelope())
        raw = {
            "id": "resp_001",
            "model": "openai/model-approved-v1",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": '{"title":"T","summary":"S"}'}],
            }],
            "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        }
        r = normalize_openai_response(raw, p)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["structured_output"]["title"], "T")
        self.assertEqual(r["evidence"]["total_tokens"], 120)
        self.assertNotIn("input_text", r["evidence"])

    def test_refusal_bad_json_model_mismatch_and_usage_missing_hold(self):
        p = prepare_openai_request(envelope())
        refusal = {
            "id": "resp_1", "model": "openai/model-approved-v1",
            "output": [{"type":"message","content":[{"type":"refusal","refusal":"no"}]}],
            "usage": {"input_tokens":1,"output_tokens":1,"total_tokens":2},
        }
        self.assertEqual(normalize_openai_response(refusal,p)["reason"], "MODEL_REFUSAL")

        mismatch = {
            "id":"resp_2","model":"other",
            "output":[{"type":"message","content":[{"type":"output_text","text":'{"title":"T","summary":"S"}'}]}],
            "usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2},
        }
        self.assertEqual(normalize_openai_response(mismatch,p)["reason"], "RESPONSE_MODEL_MISMATCH")

        no_usage = {
            "id":"resp_3","model":"openai/model-approved-v1",
            "output":[{"type":"message","content":[{"type":"output_text","text":'{"title":"T","summary":"S"}'}]}],
            "usage":{},
        }
        self.assertEqual(normalize_openai_response(no_usage,p)["reason"], "USAGE_EVIDENCE_REQUIRED")

        bad_json = {
            "id":"resp_4","model":"openai/model-approved-v1",
            "output":[{"type":"message","content":[{"type":"output_text","text":"not-json"}]}],
            "usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2},
        }
        self.assertEqual(normalize_openai_response(bad_json,p)["reason"], "STRUCTURED_OUTPUT_JSON_INVALID")


if __name__ == "__main__":
    unittest.main()
