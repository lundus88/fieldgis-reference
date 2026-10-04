from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Iterable

SCHEMA = "lom.macro-evaluation/1"
CAUSAL_SCHEMA = "lom.causal-memory-projection/1"

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"
LEARNING_DISPOSITION = "PROPOSE_ONLY"

ALLOWED_OUTCOMES = {"PASS", "FAIL", "HOLD", "ESCALATE"}
ALLOWED_TARGETS = {
    "ROUTING",
    "EVALUATION",
    "TEST_COVERAGE",
    "OBSERVABILITY",
    "NON_PROD_WORKFLOW",
}
HUMAN_ONLY_TARGETS = {
    "PRODUCTION_RELEASE",
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_DATA_MUTATION",
    "AUTHORITY_WIDENING",
    "AUTH_SECURITY_POLICY_CHANGE",
    "CUSTOMER_COMMITMENT",
    "BID_SUBMISSION",
    "PRICING_COMMITMENT",
    "CONTRACT_COMMITMENT",
    "FINANCIAL_COMMITMENT",
    "DATA_DELETION",
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _authority() -> dict[str, Any]:
    return {
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "learning_disposition": LEARNING_DISPOSITION,
        "self_apply": "FORBIDDEN",
        "memory_persistence": "NONE",
        "database_mutation": "DISABLED",
        "connector_execution": "DISABLED",
    }


def _hold(reason: str) -> dict[str, Any]:
    body = {
        "schema": SCHEMA,
        "status": "HOLD",
        "reason": reason,
        "task_health": [],
        "failure_patterns": [],
        "learning_candidates": [],
        **_authority(),
    }
    return {**body, "report_digest": digest(body)}


def _finite_unit(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _normalize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    required = {
        "trace_id",
        "project_id",
        "task_class",
        "component",
        "model_id",
        "model_version",
        "tool_id",
        "outcome",
        "correctness",
        "safety",
        "evidence_correctness",
        "tool_success",
        "latency_ms",
        "cost_usd",
        "evidence_refs",
        "independently_validated",
        "production_sensitive",
    }
    if not isinstance(trace, dict) or not required.issubset(trace):
        raise ValueError("TRACE_SCHEMA_INVALID")

    normalized = dict(trace)
    for key in (
        "trace_id",
        "project_id",
        "task_class",
        "component",
        "model_id",
        "model_version",
        "tool_id",
    ):
        normalized[key] = str(normalized.get(key) or "").strip()
        if not normalized[key]:
            raise ValueError(f"TRACE_{key.upper()}_REQUIRED")

    if normalized.get("outcome") not in ALLOWED_OUTCOMES:
        raise ValueError("TRACE_OUTCOME_INVALID")

    failure_code = str(normalized.get("failure_code") or "").strip()
    if normalized["outcome"] == "PASS" and failure_code:
        raise ValueError("PASS_TRACE_FAILURE_CODE_FORBIDDEN")
    if normalized["outcome"] != "PASS" and not failure_code:
        raise ValueError("FAILED_TRACE_FAILURE_CODE_REQUIRED")
    normalized["failure_code"] = failure_code or None

    for key in ("correctness", "safety", "evidence_correctness"):
        if not _finite_unit(normalized.get(key)):
            raise ValueError(f"TRACE_{key.upper()}_INVALID")
        normalized[key] = float(normalized[key])

    if not isinstance(normalized.get("tool_success"), bool):
        raise ValueError("TRACE_TOOL_SUCCESS_INVALID")
    if not _finite_nonnegative(normalized.get("latency_ms")):
        raise ValueError("TRACE_LATENCY_INVALID")
    if not _finite_nonnegative(normalized.get("cost_usd")):
        raise ValueError("TRACE_COST_INVALID")

    refs = sorted(
        set(
            str(x).strip()
            for x in (normalized.get("evidence_refs") or [])
            if str(x).strip()
        )
    )
    if not refs:
        raise ValueError("TRACE_EVIDENCE_REQUIRED")
    normalized["evidence_refs"] = refs

    if not isinstance(normalized.get("independently_validated"), bool):
        raise ValueError("TRACE_INDEPENDENT_VALIDATION_FLAG_INVALID")
    if normalized.get("production_sensitive") is not False:
        raise ValueError("PRODUCTION_SENSITIVE_TRACE_FORBIDDEN")

    return normalized


def _normalize_traces(traces: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [_normalize_trace(item) for item in traces]
    if not rows:
        raise ValueError("TRACE_POPULATION_REQUIRED")
    ids: set[str] = set()
    for row in rows:
        if row["trace_id"] in ids:
            raise ValueError("DUPLICATE_TRACE_ID")
        ids.add(row["trace_id"])
    return sorted(rows, key=lambda x: x["trace_id"])


def _validate_causal_projection(
    projection: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if projection is None:
        return []
    if not isinstance(projection, dict) or projection.get("schema") != CAUSAL_SCHEMA:
        raise ValueError("CAUSAL_PROJECTION_SCHEMA_INVALID")
    if projection.get("status") != "READY":
        raise ValueError("CAUSAL_PROJECTION_NOT_READY")
    if projection.get("execution_authority") != EXECUTION_AUTHORITY:
        raise ValueError("CAUSAL_PROJECTION_EXECUTION_AUTHORITY_WEAKENED")
    if projection.get("production_authority") != PRODUCTION_AUTHORITY:
        raise ValueError("CAUSAL_PROJECTION_PRODUCTION_AUTHORITY_WEAKENED")
    if projection.get("protected_main_merge") != PROTECTED_MAIN_MERGE:
        raise ValueError("CAUSAL_PROJECTION_PROTECTED_MAIN_AUTHORITY_WEAKENED")
    if projection.get("memory_persistence") != "NONE":
        raise ValueError("COMPETING_MEMORY_STORE_FORBIDDEN")

    body = {k: v for k, v in projection.items() if k != "projection_digest"}
    if projection.get("projection_digest") != digest(body):
        raise ValueError("CAUSAL_PROJECTION_DIGEST_MISMATCH")

    recovery = projection.get("recovery_records") or []
    for item in recovery:
        if (
            not isinstance(item, dict)
            or item.get("type") != "RECOVERY_CAUSAL"
            or item.get("outcome") != "RECOVERED"
            or item.get("environment") != "NON_PRODUCTION"
            or item.get("independently_validated") is not True
            or not item.get("evidence_refs")
        ):
            raise ValueError("CAUSAL_RECOVERY_RECORD_INVALID")
    return [dict(x) for x in recovery]


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return round(float(ordered[index]), 4)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _task_health(
    rows: list[dict[str, Any]],
    *,
    min_samples: int,
    min_correctness: float,
    min_safety: float,
    min_evidence_correctness: float,
    min_tool_success_rate: float,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["project_id"], row["task_class"]), []).append(row)

    result: list[dict[str, Any]] = []
    for (project_id, task_class), items in sorted(groups.items()):
        count = len(items)
        passes = sum(item["outcome"] == "PASS" for item in items)
        correctness = _mean([item["correctness"] for item in items])
        safety = _mean([item["safety"] for item in items])
        evidence_correctness = _mean([item["evidence_correctness"] for item in items])
        tool_success_rate = round(
            sum(1 for item in items if item["tool_success"]) / count, 4
        )
        status = "READY"
        reasons: list[str] = []
        if count < min_samples:
            status = "INSUFFICIENT_EVIDENCE"
            reasons.append("MIN_SAMPLE_NOT_MET")
        else:
            if correctness < min_correctness:
                reasons.append("CORRECTNESS_BELOW_GATE")
            if safety < min_safety:
                reasons.append("SAFETY_BELOW_GATE")
            if evidence_correctness < min_evidence_correctness:
                reasons.append("EVIDENCE_CORRECTNESS_BELOW_GATE")
            if tool_success_rate < min_tool_success_rate:
                reasons.append("TOOL_SUCCESS_BELOW_GATE")
            if reasons:
                status = "ALERT"

        result.append({
            "project_id": project_id,
            "task_class": task_class,
            "sample_count": count,
            "pass_rate": round(passes / count, 4),
            "correctness": correctness,
            "safety": safety,
            "evidence_correctness": evidence_correctness,
            "tool_success_rate": tool_success_rate,
            "p95_latency_ms": _p95([float(item["latency_ms"]) for item in items]),
            "total_cost_usd": round(sum(float(item["cost_usd"]) for item in items), 6),
            "independently_validated_count": sum(
                item["independently_validated"] for item in items
            ),
            "status": status,
            "reasons": reasons,
            "trace_ids": sorted(item["trace_id"] for item in items),
        })
    return result


def _recovery_index(
    recovery_records: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in recovery_records:
        key = (str(item.get("project_id") or ""), str(item.get("error_code") or ""))
        if all(key):
            index.setdefault(key, []).append(item)
    return index


def _failure_patterns(
    rows: list[dict[str, Any]],
    *,
    min_occurrences: int,
    min_failure_rate: float,
    recovery_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    task_totals: dict[tuple[str, str], int] = {}
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}

    for row in rows:
        task_key = (row["project_id"], row["task_class"])
        task_totals[task_key] = task_totals.get(task_key, 0) + 1
        if row["outcome"] != "PASS":
            key = (
                row["project_id"],
                row["task_class"],
                row["component"],
                str(row["failure_code"]),
            )
            groups.setdefault(key, []).append(row)

    recovery = _recovery_index(recovery_records)
    patterns: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        project_id, task_class, component, failure_code = key
        total = task_totals[(project_id, task_class)]
        occurrence_count = len(items)
        failure_rate = round(occurrence_count / total, 4)
        if occurrence_count < min_occurrences or failure_rate < min_failure_rate:
            continue

        causal_support = []
        for record in recovery.get((project_id, failure_code), []):
            causal_support.append({
                "record_id": record.get("record_id"),
                "action": record.get("action"),
                "lesson": record.get("lesson"),
                "evidence_refs": sorted(record.get("evidence_refs") or []),
            })

        severity = "LOW"
        if failure_rate >= 0.5:
            severity = "HIGH"
        elif failure_rate >= 0.25:
            severity = "MEDIUM"

        pattern_body = {
            "project_id": project_id,
            "task_class": task_class,
            "component": component,
            "failure_code": failure_code,
            "occurrence_count": occurrence_count,
            "task_sample_count": total,
            "failure_rate": failure_rate,
            "severity": severity,
            "trace_ids": sorted(item["trace_id"] for item in items),
            "evidence_refs": sorted({
                ref for item in items for ref in item["evidence_refs"]
            }),
            "causal_status": "CAUSAL_SUPPORTED" if causal_support else "OBSERVATIONAL",
            "causal_support": causal_support,
        }
        patterns.append({
            **pattern_body,
            "pattern_id": "macro:" + digest(pattern_body)[7:23],
        })

    return sorted(patterns, key=lambda x: x["pattern_id"])


def _learning_candidates(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for pattern in patterns:
        support = pattern.get("causal_support") or []
        if support:
            target = "NON_PROD_WORKFLOW"
            action = support[0]["action"]
            proposed_change = (
                f"Evaluate bounded reuse of independently validated recovery action "
                f"{action} for recurrent {pattern['failure_code']}."
            )
            supporting_refs = sorted({
                ref
                for item in support
                for ref in (item.get("evidence_refs") or [])
            } | set(pattern["evidence_refs"]))
        else:
            target = "EVALUATION"
            proposed_change = (
                f"Add or strengthen evaluation coverage for recurrent "
                f"{pattern['failure_code']} in {pattern['task_class']}."
            )
            supporting_refs = list(pattern["evidence_refs"])

        if target in HUMAN_ONLY_TARGETS or target not in ALLOWED_TARGETS:
            raise ValueError("LEARNING_TARGET_FORBIDDEN")

        candidate_body = {
            "target": target,
            "proposed_change": proposed_change,
            "supporting_pattern_id": pattern["pattern_id"],
            "supporting_trace_ids": pattern["trace_ids"],
            "supporting_evidence_refs": supporting_refs,
            "causal_status": pattern["causal_status"],
            "severity": pattern["severity"],
            "disposition": LEARNING_DISPOSITION,
        }
        candidates.append({
            **candidate_body,
            "candidate_id": "learn:" + digest(candidate_body)[7:23],
        })
    return sorted(candidates, key=lambda x: x["candidate_id"])


def build_macro_evaluation(
    traces: Iterable[dict[str, Any]],
    *,
    causal_projection: dict[str, Any] | None = None,
    min_samples: int = 3,
    min_occurrences: int = 2,
    min_failure_rate: float = 0.2,
    min_correctness: float = 0.9,
    min_safety: float = 0.95,
    min_evidence_correctness: float = 0.95,
    min_tool_success_rate: float = 0.95,
) -> dict[str, Any]:
    try:
        if min_samples < 1 or min_occurrences < 1:
            raise ValueError("POSITIVE_SAMPLE_GATES_REQUIRED")
        for gate in (
            min_failure_rate,
            min_correctness,
            min_safety,
            min_evidence_correctness,
            min_tool_success_rate,
        ):
            if not _finite_unit(gate):
                raise ValueError("MACRO_GATE_INVALID")

        rows = _normalize_traces(traces)
        recovery = _validate_causal_projection(causal_projection)
        health = _task_health(
            rows,
            min_samples=min_samples,
            min_correctness=min_correctness,
            min_safety=min_safety,
            min_evidence_correctness=min_evidence_correctness,
            min_tool_success_rate=min_tool_success_rate,
        )
        patterns = _failure_patterns(
            rows,
            min_occurrences=min_occurrences,
            min_failure_rate=min_failure_rate,
            recovery_records=recovery,
        )
        candidates = _learning_candidates(patterns)
    except ValueError as exc:
        return _hold(str(exc))

    body = {
        "schema": SCHEMA,
        "status": "READY",
        "reason": "MACRO_EVALUATION_READY",
        "trace_count": len(rows),
        "task_health": health,
        "failure_patterns": patterns,
        "learning_candidates": candidates,
        "recurrent_pattern_count": len(patterns),
        "learning_candidate_count": len(candidates),
        "causality_inferred_from_trace_sequence": False,
        **_authority(),
    }
    return {**body, "report_digest": digest(body)}


def validate_macro_evaluation(report: dict[str, Any]) -> dict[str, str]:
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        return {"status": "HOLD", "reason": "MACRO_EVALUATION_SCHEMA_INVALID"}
    for key, expected in (
        ("autonomous_ceiling", AUTONOMOUS_CEILING),
        ("execution_authority", EXECUTION_AUTHORITY),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("protected_main_merge", PROTECTED_MAIN_MERGE),
        ("learning_disposition", LEARNING_DISPOSITION),
    ):
        if report.get(key) != expected:
            return {"status": "HOLD", "reason": f"{key.upper()}_WEAKENED"}
    if report.get("self_apply") != "FORBIDDEN":
        return {"status": "HOLD", "reason": "SELF_APPLY_FORBIDDEN"}
    if report.get("memory_persistence") != "NONE":
        return {"status": "HOLD", "reason": "COMPETING_MEMORY_STORE_FORBIDDEN"}
    if report.get("database_mutation") != "DISABLED" or report.get("connector_execution") != "DISABLED":
        return {"status": "HOLD", "reason": "MACRO_WRITE_AUTHORITY_FORBIDDEN"}
    if report.get("causality_inferred_from_trace_sequence") is not False:
        return {"status": "HOLD", "reason": "TRACE_SEQUENCE_CAUSALITY_FORBIDDEN"}

    body = {k: v for k, v in report.items() if k != "report_digest"}
    if report.get("report_digest") != digest(body):
        return {"status": "HOLD", "reason": "MACRO_EVALUATION_DIGEST_MISMATCH"}
    if report.get("status") != "READY":
        return {"status": "HOLD", "reason": str(report.get("reason") or "MACRO_EVALUATION_HOLD")}
    return {"status": "READY", "reason": "MACRO_EVALUATION_VALID"}
