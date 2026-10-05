from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict

SCHEMA = "lom.openai-responses-adapter/1"
OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
ALLOWED_ENVIRONMENTS = {"development", "staging"}
ALLOWED_DATA_CLASSES = {"public", "internal"}
ALLOWED_CAPABILITIES = {
    "youtube.research.prepare",
    "youtube.script.generate",
    "youtube.qa.evaluate",
}
FORBIDDEN_FIELD = re.compile(r"(api[_-]?key|secret|password|access[_-]?token|refresh[_-]?token|authorization|credential)", re.I)
SECRET_VALUE = re.compile(r"(?:^|\s)(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+)", re.I)


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _find_secret(value: Any, path: str = "root") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            next_path = f"{path}.{key}"
            if FORBIDDEN_FIELD.search(str(key)):
                return next_path
            found = _find_secret(child, next_path)
            if found:
                return found
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            found = _find_secret(child, f"{path}[{idx}]")
            if found:
                return found
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        return path
    return None


def _validate_schema(schema: Dict[str, Any]) -> bool:
    if not isinstance(schema, dict):
        return False
    if schema.get("type") != "object":
        return False
    if schema.get("additionalProperties") is not False:
        return False
    props = schema.get("properties")
    required = schema.get("required")
    if not isinstance(props, dict) or not props:
        return False
    if not isinstance(required, list) or sorted(required) != sorted(props.keys()):
        return False
    return True


def prepare_openai_request(envelope: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(envelope, dict):
        return {"decision": "HOLD", "reason": "ENVELOPE_REQUIRED"}

    secret_path = _find_secret(envelope)
    if secret_path:
        return {"decision": "HOLD", "reason": "SECRET_MATERIAL_FORBIDDEN", "path": secret_path}

    required = ("request_id", "job_id", "content_id", "capability", "input_text", "route_binding", "output_schema")
    for key in required:
        value = envelope.get(key)
        if value is None or value == "":
            return {"decision": "HOLD", "reason": "ENVELOPE_INCOMPLETE", "missing": key}

    if envelope["capability"] not in ALLOWED_CAPABILITIES:
        return {"decision": "HOLD", "reason": "CAPABILITY_NOT_ALLOWED"}

    data_class = str(envelope.get("data_class") or "public")
    if data_class not in ALLOWED_DATA_CLASSES:
        return {"decision": "HOLD", "reason": "P0_DATA_CLASS_NOT_ALLOWED"}

    route = envelope["route_binding"]
    if not isinstance(route, dict):
        return {"decision": "HOLD", "reason": "ROUTE_BINDING_REQUIRED"}
    if route.get("provider") != "openai":
        return {"decision": "HOLD", "reason": "OPENAI_ROUTE_REQUIRED"}
    if route.get("authoritative_source") != "vl/model-governance":
        return {"decision": "HOLD", "reason": "AUTHORITATIVE_ROUTE_SOURCE_REQUIRED"}
    if route.get("verification_status") != "VERIFIED":
        return {"decision": "HOLD", "reason": "ROUTE_VERIFICATION_REQUIRED"}
    if route.get("certified") is not True:
        return {"decision": "HOLD", "reason": "CERTIFIED_ROUTE_REQUIRED"}
    if route.get("production_locked") is not True:
        return {"decision": "HOLD", "reason": "PRODUCTION_LOCK_REQUIRED"}
    if route.get("training") != "disabled":
        return {"decision": "HOLD", "reason": "TRAINING_DISABLED_REQUIRED"}
    if route.get("retention") not in {"none", "30_days"}:
        return {"decision": "HOLD", "reason": "RETENTION_POLICY_NOT_ALLOWED"}
    if not isinstance(route.get("decision_sha256"), str) or len(route["decision_sha256"]) != 64:
        return {"decision": "HOLD", "reason": "ROUTE_EVIDENCE_REQUIRED"}

    model = str(route.get("model_id") or "").strip()
    if not model:
        return {"decision": "HOLD", "reason": "MODEL_ID_REQUIRED"}

    environment = str(envelope.get("environment") or "development")
    if environment not in ALLOWED_ENVIRONMENTS:
        return {"decision": "HOLD", "reason": "NONPRODUCTION_ENVIRONMENT_REQUIRED"}

    max_output_tokens = envelope.get("max_output_tokens", 2000)
    if not isinstance(max_output_tokens, int) or max_output_tokens < 1 or max_output_tokens > 8000:
        return {"decision": "HOLD", "reason": "OUTPUT_TOKEN_BOUND_INVALID"}

    if not _validate_schema(envelope["output_schema"]):
        return {"decision": "HOLD", "reason": "STRICT_OUTPUT_SCHEMA_REQUIRED"}

    request_core = {
        "schema": SCHEMA,
        "request_id": str(envelope["request_id"]),
        "job_id": str(envelope["job_id"]),
        "content_id": str(envelope["content_id"]),
        "capability": envelope["capability"],
        "data_class": data_class,
        "environment": environment,
        "provider": "openai",
        "model": model,
        "route_decision_sha256": route["decision_sha256"],
        "route_retention": route["retention"],
        "input_sha256": canonical_hash(envelope["input_text"]),
        "output_schema_sha256": canonical_hash(envelope["output_schema"]),
        "max_output_tokens": max_output_tokens,
        "production_locked": True,
        "credential_delivery": "BROKER_INJECTED_SERVER_SIDE",
    }
    request_digest = canonical_hash(request_core)

    body = {
        "model": model,
        "input": envelope["input_text"],
        "store": False,
        "max_output_tokens": max_output_tokens,
        "tools": [],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "lom_youtube_structured_output",
                "strict": True,
                "schema": envelope["output_schema"],
            }
        },
        "metadata": {
            "request_id": str(envelope["request_id"]),
            "job_id": str(envelope["job_id"]),
            "content_id": str(envelope["content_id"]),
            "capability": envelope["capability"],
        },
    }

    return {
        "decision": "ALLOW",
        "state": "REQUEST_PREPARED",
        "request_digest": request_digest,
        "http": {
            "method": "POST",
            "endpoint": OPENAI_RESPONSES_ENDPOINT,
            "auth_mode": "BROKER_INJECTED_BEARER",
            "body": body,
        },
        "evidence": request_core,
    }


def authorize_nonprod_live_call(prepared: Dict[str, Any], broker_attestation: Dict[str, Any], approval_verification: Dict[str, Any]) -> Dict[str, Any]:
    if prepared.get("decision") != "ALLOW":
        return {"decision": "HOLD", "reason": "PREPARED_REQUEST_REQUIRED"}
    request_digest = prepared.get("request_digest")
    if not request_digest:
        return {"decision": "HOLD", "reason": "REQUEST_DIGEST_REQUIRED"}

    if not isinstance(broker_attestation, dict):
        return {"decision": "HOLD", "reason": "BROKER_ATTESTATION_REQUIRED"}
    if broker_attestation.get("broker_id") != "lom-openai-nonprod":
        return {"decision": "HOLD", "reason": "BROKER_ID_MISMATCH"}
    if broker_attestation.get("environment") not in ALLOWED_ENVIRONMENTS:
        return {"decision": "HOLD", "reason": "BROKER_NONPROD_REQUIRED"}
    if broker_attestation.get("secret_injected_server_side") is not True:
        return {"decision": "HOLD", "reason": "SERVER_SIDE_SECRET_INJECTION_REQUIRED"}
    if broker_attestation.get("worker_secret_access") is not False:
        return {"decision": "HOLD", "reason": "WORKER_SECRET_ACCESS_FORBIDDEN"}
    if broker_attestation.get("production_locked") is not True:
        return {"decision": "HOLD", "reason": "BROKER_PRODUCTION_LOCK_REQUIRED"}

    if not isinstance(approval_verification, dict):
        return {"decision": "HOLD", "reason": "INDEPENDENT_APPROVAL_VERIFICATION_REQUIRED"}
    if approval_verification.get("status") != "VERIFIED":
        return {"decision": "HOLD", "reason": "APPROVAL_NOT_VERIFIED"}
    if approval_verification.get("principal_type") != "human":
        return {"decision": "HOLD", "reason": "HUMAN_APPROVAL_REQUIRED"}
    if approval_verification.get("request_digest") != request_digest:
        return {"decision": "HOLD", "reason": "APPROVAL_DIGEST_MISMATCH"}
    if not str(approval_verification.get("evidence_ref") or "").strip():
        return {"decision": "HOLD", "reason": "APPROVAL_EVIDENCE_REQUIRED"}

    return {
        "decision": "ALLOW",
        "state": "NONPROD_LIVE_CALL_AUTHORIZED",
        "request_digest": request_digest,
        "broker_id": broker_attestation["broker_id"],
        "production_locked": True,
        "paid_call_authority": "SINGLE_BOUNDED_REQUEST",
        "approval_evidence_ref": approval_verification["evidence_ref"],
    }


def normalize_openai_response(raw: Dict[str, Any], prepared: Dict[str, Any]) -> Dict[str, Any]:
    if prepared.get("decision") != "ALLOW":
        return {"decision": "HOLD", "reason": "PREPARED_REQUEST_REQUIRED"}
    if not isinstance(raw, dict):
        return {"decision": "HOLD", "reason": "RESPONSE_REQUIRED"}

    secret_path = _find_secret(raw)
    if secret_path:
        return {"decision": "HOLD", "reason": "SECRET_MATERIAL_IN_RESPONSE", "path": secret_path}

    response_id = str(raw.get("id") or "").strip()
    model = str(raw.get("model") or "").strip()
    if not response_id or not model:
        return {"decision": "HOLD", "reason": "RESPONSE_IDENTITY_REQUIRED"}

    expected_model = prepared["http"]["body"]["model"]
    if model != expected_model:
        return {"decision": "HOLD", "reason": "RESPONSE_MODEL_MISMATCH"}

    usage = raw.get("usage") or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    if not all(isinstance(v, int) and v >= 0 for v in (input_tokens, output_tokens, total_tokens)):
        return {"decision": "HOLD", "reason": "USAGE_EVIDENCE_REQUIRED"}

    refusal = False
    texts = []
    for item in raw.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "refusal":
                refusal = True
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])

    if refusal:
        return {"decision": "HOLD", "reason": "MODEL_REFUSAL"}
    if len(texts) != 1:
        return {"decision": "HOLD", "reason": "SINGLE_STRUCTURED_OUTPUT_REQUIRED"}

    try:
        parsed = json.loads(texts[0])
    except json.JSONDecodeError:
        return {"decision": "HOLD", "reason": "STRUCTURED_OUTPUT_JSON_INVALID"}

    if not isinstance(parsed, dict):
        return {"decision": "HOLD", "reason": "STRUCTURED_OUTPUT_OBJECT_REQUIRED"}

    expected_keys = set(prepared["http"]["body"]["text"]["format"]["schema"]["properties"].keys())
    if set(parsed.keys()) != expected_keys:
        return {"decision": "HOLD", "reason": "STRUCTURED_OUTPUT_SCHEMA_KEY_MISMATCH"}

    evidence = {
        "schema": "lom.openai-response-evidence/1",
        "request_digest": prepared["request_digest"],
        "response_id": response_id,
        "provider": "openai",
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "output_sha256": canonical_hash(parsed),
        "production_locked": True,
    }
    evidence["evidence_sha256"] = canonical_hash(evidence)

    return {
        "decision": "ALLOW",
        "state": "RESPONSE_VERIFIED",
        "structured_output": parsed,
        "evidence": evidence,
    }
