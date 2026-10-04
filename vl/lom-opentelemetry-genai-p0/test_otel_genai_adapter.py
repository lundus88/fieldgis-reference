import copy
import unittest

from otel_genai_adapter import build_otel_genai_envelope, validate_otel_genai_envelope


def trace(trace_id="t1", *, outcome="PASS", failure_code=None, tool_success=True):
    return {
        "trace_id": trace_id,
        "project_id": "vl",
        "task_class": "CODING_DEBUGGING",
        "component": "planner",
        "provider": "openai",
        "model_id": "model-x",
        "model_version": "v1",
        "response_model": "model-x:v1",
        "operation": "chat",
        "tool_id": "github",
        "outcome": outcome,
        "failure_code": failure_code,
        "correctness": 1.0,
        "safety": 1.0,
        "evidence_correctness": 1.0,
        "tool_success": tool_success,
        "latency_ms": 250.0,
        "cost_usd": 0.0123,
        "input_tokens": 100,
        "output_tokens": 40,
        "evidence_refs": [f"urn:trace:{trace_id}"],
        "independently_validated": True,
        "production_sensitive": False,
    }


class OTelGenAIAdapterTests(unittest.TestCase):
    def test_builds_model_and_tool_spans_without_content(self):
        out = build_otel_genai_envelope([trace()])
        self.assertEqual(out["status"], "READY")
        self.assertEqual(out["trace_count"], 1)
        self.assertEqual(out["span_count"], 2)
        self.assertFalse(out["prompt_completion_content_exported"])
        model = out["spans"][0]
        tool = out["spans"][1]
        self.assertEqual(model["attributes"]["gen_ai.operation.name"], "chat")
        self.assertEqual(model["attributes"]["gen_ai.usage.input_tokens"], 100)
        self.assertEqual(model["attributes"]["gen_ai.usage.output_tokens"], 40)
        self.assertEqual(tool["attributes"]["gen_ai.operation.name"], "execute_tool")
        self.assertEqual(tool["attributes"]["gen_ai.tool.name"], "github")
        self.assertEqual(validate_otel_genai_envelope(out)["status"], "READY")

    def test_sensitive_prompt_content_fails_closed(self):
        row = trace()
        row["prompt"] = "private customer text"
        out = build_otel_genai_envelope([row])
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "SENSITIVE_CONTENT_FIELD_FORBIDDEN:prompt")

    def test_system_instruction_content_fails_closed(self):
        row = trace()
        row["system_instructions"] = "secret system instruction"
        out = build_otel_genai_envelope([row])
        self.assertEqual(out["status"], "HOLD")

    def test_production_sensitive_trace_fails_closed(self):
        row = trace()
        row["production_sensitive"] = True
        out = build_otel_genai_envelope([row])
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "PRODUCTION_SENSITIVE_TELEMETRY_FORBIDDEN")

    def test_failure_sets_error_type_without_error_content(self):
        row = trace(outcome="FAIL", failure_code="E_TOOL", tool_success=False)
        out = build_otel_genai_envelope([row])
        self.assertEqual(out["status"], "READY")
        model = out["spans"][0]
        tool = out["spans"][1]
        self.assertEqual(model["status_code"], "ERROR")
        self.assertEqual(model["attributes"]["error.type"], "E_TOOL")
        self.assertEqual(tool["status_code"], "ERROR")
        self.assertEqual(tool["attributes"]["error.type"], "E_TOOL")

    def test_duplicate_trace_fails_closed(self):
        out = build_otel_genai_envelope([trace("t1"), trace("t1")])
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "DUPLICATE_TRACE_ID")

    def test_trace_order_is_deterministic(self):
        a = build_otel_genai_envelope([trace("t1"), trace("t2")])
        b = build_otel_genai_envelope([trace("t2"), trace("t1")])
        self.assertEqual(a["envelope_digest"], b["envelope_digest"])

    def test_tamper_is_detected(self):
        out = build_otel_genai_envelope([trace()])
        tampered = copy.deepcopy(out)
        tampered["span_count"] = 99
        self.assertEqual(
            validate_otel_genai_envelope(tampered)["reason"],
            "OTEL_GENAI_DIGEST_MISMATCH",
        )

    def test_live_export_is_forbidden_in_p0(self):
        out = build_otel_genai_envelope([trace()])
        out["network_export"] = "ENABLED"
        self.assertEqual(
            validate_otel_genai_envelope(out)["reason"],
            "LIVE_OTLP_EXPORT_FORBIDDEN_P0",
        )


if __name__ == "__main__":
    unittest.main()
