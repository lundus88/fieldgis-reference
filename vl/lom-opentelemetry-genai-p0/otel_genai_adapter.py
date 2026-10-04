from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Iterable

SCHEMA = "lom.otel-genai-adapter/1"
SEMCONV_BASELINE = "OpenTelemetry-semconv-1.44.0+GenAI-current-2026-10-04"

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"

ALLOWED_OUTCOMES = {"PASS", "FAIL", "HOLD", "ESCALATE"}
ALLOWED_OPERATIONS = {
    "chat",
    "generate_content",
    "embeddings",
    "invoke_agent",
    "invoke_workflow",
    "retrieval",
}
FORBIDDEN_CONTENT_KEYS = {
    "prompt",
    "prompts",
    "completion",
    "completions",
    "input_messages",
    "output_messages",
    "system_instructions",
    "retrieval_query_text",
    "tool_arguments",
    "tool_results",
    "request_body",
    "response_body",
    "secret",
    "credential",
    "api_key",
    "access_token",
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _finite_unit(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _clean_provider(value: Any) -> str:
    provider = str(value or "").strip().lower()
    if not provider:
        raise ValueError("GENAI_PROVIDER_REQUIRED")
    return provider


def _validate_no_content_capture(trace: dict[str, Any]) -> None:
    for key in FORBIDDEN_CONTENT_KEYS:
        if key in trace and trace.get(key) not in (None, "", [], {}, ()):
            raise ValueError(f"SENSITIVE_CONTENT_FIELD_FORBIDDEN:{key}")


def _normalize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    required = {
        "trace_id",
        "project_id",
        "task_class",
        "component",
        "provider",
        "model_id",
        "model_version",
        "operation",
        "tool_id",
        "outcome",
        "correctness",
        "safety",
        "evidence_correctness",
        "tool_success",
        "latency_ms",
        "cost_usd",
        "input_tokens",
        "output_tokens",
        "evidence_refs",
        "independently_validated",
        "production_sensitive",
    }
    if not isinstance(trace, dict) or not required.issubset(trace):
        raise ValueError("TRACE_SCHEMA_INVALID")

    _validate_no_content_capture(trace)

    row = dict(trace)
    for key in (
        "trace_id",
        "project_id",
        "task_class",
        "component",
        "model_id",
        "model_version",
        "tool_id",
    ):
        row[key] = str(row.get(key) or "").strip()
        if not row[key]:
            raise ValueError(f"TRACE_{key.upper()}_REQUIRED")

    row["provider"] = _clean_provider(row.get("provider"))
    row["operation"] = str(row.get("operation") or "").strip()
    if row["operation"] not in ALLOWED_OPERATIONS:
        raise ValueError("GENAI_OPERATION_INVALID")

    if row.get("outcome") not in ALLOWED_OUTCOMES:
        raise ValueError("TRACE_OUTCOME_INVALID")

    failure_code = str(row.get("failure_code") or "").strip()
    if row["outcome"] == "PASS" and failure_code:
        raise ValueError("PASS_TRACE_FAILURE_CODE_FORBIDDEN")
    if row["outcome"] != "PASS" and not failure_code:
        raise ValueError("FAILED_TRACE_FAILURE_CODE_REQUIRED")
    row["failure_code"] = failure_code or None

    for key in ("correctness", "safety", "evidence_correctness"):
        if not _finite_unit(row.get(key)):
            raise ValueError(f"TRACE_{key.upper()}_INVALID")
        row[key] = float(row[key])

    if not isinstance(row.get("tool_success"), bool):
        raise ValueError("TRACE_TOOL_SUCCESS_INVALID")
    if not _finite_nonnegative(row.get("latency_ms")):
        raise ValueError("TRACE_LATENCY_INVALID")
    if not _finite_nonnegative(row.get("cost_usd")):
        raise ValueError("TRACE_COST_INVALID")

    for key in ("input_tokens", "output_tokens"):
        value = row.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"TRACE_{key.upper()}_INVALID")

    refs = sorted(
        set(
            str(x).strip()
            for x in (row.get("evidence_refs") or [])
            if str(x).strip()
        )
    )
    if not refs:
        raise ValueError("TRACE_EVIDENCE_REQUIRED")
    row["evidence_refs"] = refs

    if not isinstance(row.get("independently_validated"), bool):
        raise ValueError("TRACE_INDEPENDENT_VALIDATION_FLAG_INVALID")
    if row.get("production_sensitive") is not False:
        raise ValueError("PRODUCTION_SENSITIVE_TELEMETRY_FORBIDDEN")

    response_model = str(row.get("response_model") or "").strip()
    row["response_model"] = response_model or f"{row['model_id']}:{row['model_version']}"
    return row


def _status(row: dict[str, Any]) -> tuple[str, str | None]:
    if row["outcome"] == "PASS":
        return "OK", None
    if row["outcome"] == "FAIL":
        return "ERROR", row["failure_code"]
    return "UNSET", row["failure_code"]


def _model_span(row: dict[str, Any]) -> dict[str, Any]:
    status_code, error_type = _status(row)
    attributes: dict[str, Any] = {
        "gen_ai.operation.name": row["operation"],
        "gen_ai.provider.name": row["provider"],
        "gen_ai.request.model": f"{row['model_id']}:{row['model_version']}",
        "gen_ai.response.model": row["response_model"],
        "gen_ai.usage.input_tokens": row["input_tokens"],
        "gen_ai.usage.output_tokens": row["output_tokens"],
        "lom.project.id": row["project_id"],
        "lom.task.class": row["task_class"],
        "lom.trace.id": row["trace_id"],
        "lom.component": row["component"],
        "lom.evidence.refs": row["evidence_refs"],
        "lom.independently_validated": row["independently_validated"],
        "lom.correctness": row["correctness"],
        "lom.safety": row["safety"],
        "lom.evidence_correctness": row["evidence_correctness"],
        "lom.cost.usd": round(float(row["cost_usd"]), 8),
        "lom.outcome": row["outcome"],
    }
    if error_type:
        attributes["error.type"] = error_type
        attributes["lom.failure.code"] = error_type

    body = {
        "span_name": f"{row['operation']} {row['model_id']}",
        "span_kind": "CLIENT",
        "status_code": status_code,
        "duration_ms": round(float(row["latency_ms"]), 4),
        "attributes": attributes,
        "events": [],
        "content_capture": False,
    }
    return {**body, "span_digest": digest(body)}


def _tool_span(row: dict[str, Any]) -> dict[str, Any]:
    status_code = "OK" if row["tool_success"] else "ERROR"
    attributes: dict[str, Any] = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.provider.name": row["provider"],
        "gen_ai.tool.name": row["tool_id"],
        "gen_ai.tool.type": "function",
        "lom.project.id": row["project_id"],
        "lom.task.class": row["task_class"],
        "lom.trace.id": row["trace_id"],
        "lom.evidence.refs": row["evidence_refs"],
        "lom.tool.success": row["tool_success"],
    }
    if not row["tool_success"] and row["failure_code"]:
        attributes["error.type"] = row["failure_code"]
        attributes["lom.failure.code"] = row["failure_code"]

    body = {
        "span_name": f"execute_tool {row['tool_id']}",
        "span_kind": "INTERNAL",
        "status_code": status_code,
        "attributes": attributes,
        "events": [],
        "content_capture": False,
    }
    return {**body, "span_digest": digest(body)}


def build_otel_genai_envelope(traces: Iterable[dict[str, Any]]) -> dict[str, Any]:
    try:
        rows = [_normalize_trace(item) for item in traces]
        if not rows:
            raise ValueError("TRACE_POPULATION_REQUIRED")
        seen: set[str] = set()
        for row in rows:
            if row["trace_id"] in seen:
                raise ValueError("DUPLICATE_TRACE_ID")
            seen.add(row["trace_id"])
        rows.sort(key=lambda x: x["trace_id"])
    except ValueError as exc:
        body = {
            "schema": SCHEMA,
            "status": "HOLD",
            "reason": str(exc),
            "semconv_baseline": SEMCONV_BASELINE,
            "spans": [],
            "prompt_completion_content_exported": False,
            "network_export": "DISABLED",
            "telemetry_persistence": "NONE",
            "autonomous_ceiling": AUTONOMOUS_CEILING,
            "execution_authority": EXECUTION_AUTHORITY,
            "production_authority": PRODUCTION_AUTHORITY,
            "protected_main_merge": PROTECTED_MAIN_MERGE,
        }
        return {**body, "envelope_digest": digest(body)}

    spans: list[dict[str, Any]] = []
    for row in rows:
        spans.append(_model_span(row))
        spans.append(_tool_span(row))

    body = {
        "schema": SCHEMA,
        "status": "READY",
        "reason": "OTEL_GENAI_ENVELOPE_READY",
        "semconv_baseline": SEMCONV_BASELINE,
        "trace_count": len(rows),
        "span_count": len(spans),
        "spans": spans,
        "prompt_completion_content_exported": False,
        "system_instruction_content_exported": False,
        "tool_argument_result_content_exported": False,
        "retrieval_query_content_exported": False,
        "network_export": "DISABLED",
        "telemetry_persistence": "NONE",
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
    }
    return {**body, "envelope_digest": digest(body)}


def validate_otel_genai_envelope(envelope: dict[str, Any]) -> dict[str, str]:
    if not isinstance(envelope, dict) or envelope.get("schema") != SCHEMA:
        return {"status": "HOLD", "reason": "OTEL_GENAI_SCHEMA_INVALID"}

    for key, expected in (
        ("autonomous_ceiling", AUTONOMOUS_CEILING),
        ("execution_authority", EXECUTION_AUTHORITY),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("protected_main_merge", PROTECTED_MAIN_MERGE),
    ):
        if envelope.get(key) != expected:
            return {"status": "HOLD", "reason": f"{key.upper()}_WEAKENED"}

    if envelope.get("network_export") != "DISABLED":
        return {"status": "HOLD", "reason": "LIVE_OTLP_EXPORT_FORBIDDEN_P0"}
    if envelope.get("telemetry_persistence") != "NONE":
        return {"status": "HOLD", "reason": "TELEMETRY_PERSISTENCE_FORBIDDEN_P0"}

    for key in (
        "prompt_completion_content_exported",
        "system_instruction_content_exported",
        "tool_argument_result_content_exported",
        "retrieval_query_content_exported",
    ):
        if envelope.get(key) is not False:
            return {"status": "HOLD", "reason": "SENSITIVE_CONTENT_EXPORT_FORBIDDEN_P0"}

    body = {k: v for k, v in envelope.items() if k != "envelope_digest"}
    if envelope.get("envelope_digest") != digest(body):
        return {"status": "HOLD", "reason": "OTEL_GENAI_DIGEST_MISMATCH"}

    if envelope.get("status") != "READY":
        return {"status": "HOLD", "reason": str(envelope.get("reason") or "OTEL_GENAI_HOLD")}

    for span in envelope.get("spans") or []:
        span_body = {k: v for k, v in span.items() if k != "span_digest"}
        if span.get("span_digest") != digest(span_body):
            return {"status": "HOLD", "reason": "OTEL_SPAN_DIGEST_MISMATCH"}
        if span.get("content_capture") is not False:
            return {"status": "HOLD", "reason": "OTEL_SPAN_CONTENT_CAPTURE_FORBIDDEN"}

    return {"status": "READY", "reason": "OTEL_GENAI_ENVELOPE_VALID"}
