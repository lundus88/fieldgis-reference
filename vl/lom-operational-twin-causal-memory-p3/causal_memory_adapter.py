from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Iterable

CAUSAL_SCHEMA = "lom.causal-memory-projection/1"
WORLD_SCHEMA = "lom.world-state-graph/1"

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"

ALLOWED_LEDGER_STATES = {
    "PLANNED", "RUNNING", "VALIDATING", "REMEDIATING",
    "COMPLETE", "HOLD", "ESCALATE", "FAIL",
}
ALLOWED_RECOVERY_OUTCOMES = {
    "RECOVERED", "FAILED", "FAILED_VALIDATION", "HOLD", "ESCALATE"
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _plain_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def _authority() -> dict[str, Any]:
    return {
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "self_approval": "FORBIDDEN",
        "database_mutation": "DISABLED",
        "connector_execution": "DISABLED",
        "memory_persistence": "NONE",
    }


def _hold(reason: str, *, violations: Iterable[str] = ()) -> dict[str, Any]:
    body = {
        "schema": CAUSAL_SCHEMA,
        "status": "HOLD",
        "reason": reason,
        "causal_records": [],
        "recovery_records": [],
        "historical_recovery_records": [],
        "violations": sorted(set(str(x) for x in violations if x)),
        **_authority(),
    }
    return {**body, "projection_digest": digest(body)}


def validate_world_graph(graph: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if not isinstance(graph, dict) or graph.get("schema") != WORLD_SCHEMA:
        raise ValueError("WORLD_GRAPH_SCHEMA_INVALID")
    if graph.get("status") != "READY":
        raise ValueError("WORLD_GRAPH_NOT_READY")
    if graph.get("execution_authority") != EXECUTION_AUTHORITY:
        raise ValueError("WORLD_GRAPH_EXECUTION_AUTHORITY_WEAKENED")
    if graph.get("production_authority") != PRODUCTION_AUTHORITY:
        raise ValueError("WORLD_GRAPH_PRODUCTION_AUTHORITY_WEAKENED")
    if graph.get("protected_main_merge") != PROTECTED_MAIN_MERGE:
        raise ValueError("WORLD_GRAPH_PROTECTED_MAIN_AUTHORITY_WEAKENED")
    if graph.get("database_mutation") != "DISABLED" or graph.get("connector_execution") != "DISABLED":
        raise ValueError("WORLD_GRAPH_WRITE_AUTHORITY_WEAKENED")
    if not graph.get("graph_digest"):
        raise ValueError("WORLD_GRAPH_DIGEST_REQUIRED")
    body = {k: v for k, v in graph.items() if k != "graph_digest"}
    if graph["graph_digest"] != digest(body):
        raise ValueError("WORLD_GRAPH_DIGEST_MISMATCH")

    projects: dict[str, dict[str, Any]] = {}
    objectives: dict[str, str] = {}
    for node in graph.get("nodes") or []:
        if node.get("type") == "PROJECT":
            project_id = str(node.get("project_id") or "")
            if not project_id or project_id in projects:
                raise ValueError("WORLD_GRAPH_PROJECT_NODE_INVALID")
            projects[project_id] = dict(node)
        elif node.get("type") == "OBJECTIVE":
            objective_id = str(node.get("objective_id") or "")
            project_id = str(node.get("project_id") or "")
            if not objective_id or not project_id or objective_id in objectives:
                raise ValueError("WORLD_GRAPH_OBJECTIVE_NODE_INVALID")
            objectives[objective_id] = project_id
    if not projects or not objectives:
        raise ValueError("WORLD_GRAPH_NODES_REQUIRED")
    return projects, objectives


def validate_event_ledger(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows = [dict(x) for x in events]
    if not rows:
        raise ValueError("EVENT_LEDGER_REQUIRED")

    index: dict[str, dict[str, Any]] = {}
    prev_hash = "GENESIS"
    for expected_sequence, event in enumerate(rows, start=1):
        if event.get("sequence") != expected_sequence:
            raise ValueError("EVENT_LEDGER_SEQUENCE_INVALID")
        if event.get("prev_hash") != prev_hash:
            raise ValueError("EVENT_LEDGER_CHAIN_INVALID")
        if event.get("to_state") not in ALLOWED_LEDGER_STATES:
            raise ValueError("EVENT_LEDGER_STATE_INVALID")
        stored_hash = str(event.get("event_hash") or "")
        if not stored_hash:
            raise ValueError("EVENT_HASH_REQUIRED")
        candidate = dict(event)
        candidate.pop("event_hash", None)
        if _plain_hash(candidate) != stored_hash:
            raise ValueError("EVENT_LEDGER_HASH_INVALID")
        if stored_hash in index:
            raise ValueError("DUPLICATE_EVENT_HASH")
        index[stored_hash] = event
        prev_hash = stored_hash
    return index


def _decision_index(decisions: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    required = {"decision_id", "action", "evidence_state", "outcome", "human_verdict", "rationale"}
    for row in decisions:
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError("DECISION_RECORD_INVALID")
        decision_id = str(row.get("decision_id") or "").strip()
        if not decision_id:
            raise ValueError("DECISION_ID_REQUIRED")
        if decision_id in out:
            raise ValueError("DUPLICATE_DECISION_ID")
        out[decision_id] = dict(row)
    return out


def _valid_confidence(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _causal_records(
    *,
    projects: dict[str, dict[str, Any]],
    objectives: dict[str, str],
    event_index: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    bindings: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for binding in bindings:
        if not isinstance(binding, dict):
            raise ValueError("CAUSAL_BINDING_INVALID")
        binding_id = str(binding.get("binding_id") or "").strip()
        project_id = str(binding.get("project_id") or "").strip()
        objective_id = str(binding.get("objective_id") or "").strip()
        decision_id = str(binding.get("decision_id") or "").strip()
        event_hash = str(binding.get("event_hash") or "").strip()
        cause = str(binding.get("cause") or "").strip()
        lesson = str(binding.get("lesson") or "").strip()
        refs = sorted(set(str(x).strip() for x in (binding.get("evidence_refs") or []) if str(x).strip()))
        confidence = binding.get("causal_confidence")

        if not binding_id or binding_id in seen:
            raise ValueError("CAUSAL_BINDING_ID_INVALID")
        seen.add(binding_id)
        if project_id not in projects:
            raise ValueError("CAUSAL_PROJECT_NOT_REGISTERED")
        if objectives.get(objective_id) != project_id:
            raise ValueError("CAUSAL_OBJECTIVE_SCOPE_MISMATCH")
        decision = decisions.get(decision_id)
        if decision is None:
            raise ValueError("CAUSAL_DECISION_NOT_REGISTERED")
        event = event_index.get(event_hash)
        if event is None:
            raise ValueError("CAUSAL_EVENT_NOT_REGISTERED")
        if str(event.get("objective_id") or "") != objective_id:
            raise ValueError("CAUSAL_EVENT_OBJECTIVE_MISMATCH")
        if str(event.get("action_id") or "") != str(decision.get("action") or ""):
            raise ValueError("CAUSAL_ACTION_MISMATCH")
        if not cause or not lesson:
            raise ValueError("CAUSE_AND_LESSON_REQUIRED")
        if not refs:
            raise ValueError("CAUSAL_EVIDENCE_REQUIRED")
        if binding.get("independently_validated") is not True:
            raise ValueError("CAUSAL_INDEPENDENT_VALIDATION_REQUIRED")
        if not _valid_confidence(confidence):
            raise ValueError("CAUSAL_CONFIDENCE_INVALID")
        if decision.get("evidence_state") in {"MISSING", "CONTRADICTORY", "STALE", "UNKNOWN"}:
            raise ValueError("DECISION_EVIDENCE_NOT_READY")

        record = {
            "record_id": f"decision-causal:{binding_id}",
            "type": "DECISION_CAUSAL",
            "project_id": project_id,
            "objective_id": objective_id,
            "decision_id": decision_id,
            "action": decision["action"],
            "ledger_event_hash": event_hash,
            "ledger_to_state": event.get("to_state"),
            "decision_outcome": decision.get("outcome"),
            "human_verdict": decision.get("human_verdict"),
            "cause": cause,
            "lesson": lesson,
            "evidence_refs": refs,
            "causal_confidence": float(confidence),
            "independently_validated": True,
        }
        records.append(record)

    return sorted(records, key=lambda x: x["record_id"])


def _failure_fingerprint(signal: dict[str, Any]) -> str:
    payload = {
        "project_id": signal.get("project_id"),
        "component": signal.get("component"),
        "failure_class": signal.get("failure_class"),
        "error_code": signal.get("error_code"),
        "environment": signal.get("environment"),
    }
    return _plain_hash(payload)


def _recovery_records(
    *,
    projects: dict[str, dict[str, Any]],
    failure_signals: Iterable[dict[str, Any]],
    recovery_attempts: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    failures: dict[str, dict[str, Any]] = {}
    for signal in failure_signals:
        required = {
            "failure_id", "run_id", "project_id", "component", "failure_class",
            "error_code", "environment", "risk", "reversible",
            "evidence_refs", "timestamp_epoch",
        }
        if not isinstance(signal, dict) or not required.issubset(signal):
            raise ValueError("FAILURE_SIGNAL_INVALID")
        project_id = str(signal.get("project_id") or "")
        if project_id not in projects:
            raise ValueError("FAILURE_PROJECT_NOT_REGISTERED")
        if signal.get("environment") not in {"NON_PRODUCTION", "PRODUCTION"}:
            raise ValueError("FAILURE_ENVIRONMENT_INVALID")
        if not signal.get("evidence_refs"):
            raise ValueError("FAILURE_EVIDENCE_REQUIRED")
        fp = _failure_fingerprint(signal)
        if fp in failures and failures[fp] != signal:
            raise ValueError("FAILURE_FINGERPRINT_COLLISION")
        failures[fp] = dict(signal)

    known_good: list[dict[str, Any]] = []
    historical: list[dict[str, Any]] = []
    seen_attempts: set[str] = set()

    for attempt in recovery_attempts:
        required = {
            "attempt_id", "run_id", "failure_fingerprint", "action", "outcome",
            "evidence_refs", "independently_validated", "timestamp_epoch",
        }
        if not isinstance(attempt, dict) or not required.issubset(attempt):
            raise ValueError("RECOVERY_ATTEMPT_INVALID")
        attempt_id = str(attempt.get("attempt_id") or "").strip()
        if not attempt_id or attempt_id in seen_attempts:
            raise ValueError("RECOVERY_ATTEMPT_ID_INVALID")
        seen_attempts.add(attempt_id)
        fp = str(attempt.get("failure_fingerprint") or "")
        signal = failures.get(fp)
        if signal is None:
            raise ValueError("RECOVERY_FAILURE_NOT_REGISTERED")
        outcome = attempt.get("outcome")
        if outcome not in ALLOWED_RECOVERY_OUTCOMES:
            raise ValueError("RECOVERY_OUTCOME_INVALID")
        refs = sorted(set(str(x).strip() for x in (attempt.get("evidence_refs") or []) if str(x).strip()))
        if not refs:
            raise ValueError("RECOVERY_EVIDENCE_REQUIRED")

        base = {
            "record_id": f"recovery:{attempt_id}",
            "type": "RECOVERY_CAUSAL" if outcome == "RECOVERED" else "RECOVERY_HISTORY",
            "project_id": signal["project_id"],
            "failure_fingerprint": fp,
            "component": signal["component"],
            "failure_class": signal["failure_class"],
            "error_code": signal["error_code"],
            "environment": signal["environment"],
            "action": attempt["action"],
            "outcome": outcome,
            "evidence_refs": refs,
            "independently_validated": bool(attempt.get("independently_validated")),
        }

        if outcome == "RECOVERED":
            if signal.get("environment") != "NON_PRODUCTION":
                raise ValueError("PRODUCTION_RECOVERY_CAUSAL_PROMOTION_FORBIDDEN")
            if attempt.get("independently_validated") is not True:
                raise ValueError("RECOVERY_REQUIRES_INDEPENDENT_VALIDATION")
            base["lesson"] = (
                f"Independently validated recovery action {attempt['action']} "
                f"recovered failure {signal['failure_class']}:{signal['error_code']}"
            )
            known_good.append(base)
        else:
            historical.append(base)

    return (
        sorted(known_good, key=lambda x: x["record_id"]),
        sorted(historical, key=lambda x: x["record_id"]),
    )


def build_causal_memory_projection(
    world_graph: dict[str, Any],
    event_ledger_events: Iterable[dict[str, Any]],
    decision_records: Iterable[dict[str, Any]],
    *,
    causal_bindings: Iterable[dict[str, Any]] = (),
    failure_signals: Iterable[dict[str, Any]] = (),
    recovery_attempts: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    try:
        projects, objectives = validate_world_graph(world_graph)
        event_index = validate_event_ledger(event_ledger_events)
        decisions = _decision_index(decision_records)
        causal = _causal_records(
            projects=projects,
            objectives=objectives,
            event_index=event_index,
            decisions=decisions,
            bindings=causal_bindings,
        )
        recovery, recovery_history = _recovery_records(
            projects=projects,
            failure_signals=failure_signals,
            recovery_attempts=recovery_attempts,
        )
    except ValueError as exc:
        return _hold(str(exc))

    body = {
        "schema": CAUSAL_SCHEMA,
        "status": "READY",
        "reason": "EVIDENCE_BACKED_CAUSAL_MEMORY_READY",
        "world_graph_digest": world_graph["graph_digest"],
        "causal_records": causal,
        "recovery_records": recovery,
        "historical_recovery_records": recovery_history,
        "causal_record_count": len(causal),
        "known_good_recovery_count": len(recovery),
        "historical_recovery_count": len(recovery_history),
        "causality_inferred_from_sequence": False,
        **_authority(),
    }
    return {**body, "projection_digest": digest(body)}


def validate_causal_memory_projection(projection: dict[str, Any]) -> dict[str, str]:
    if not isinstance(projection, dict) or projection.get("schema") != CAUSAL_SCHEMA:
        return {"status": "HOLD", "reason": "CAUSAL_PROJECTION_SCHEMA_INVALID"}
    for key, expected in (
        ("autonomous_ceiling", AUTONOMOUS_CEILING),
        ("execution_authority", EXECUTION_AUTHORITY),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("protected_main_merge", PROTECTED_MAIN_MERGE),
    ):
        if projection.get(key) != expected:
            return {"status": "HOLD", "reason": f"{key.upper()}_WEAKENED"}
    if projection.get("database_mutation") != "DISABLED" or projection.get("connector_execution") != "DISABLED":
        return {"status": "HOLD", "reason": "CAUSAL_PROJECTION_WRITE_AUTHORITY_FORBIDDEN"}
    if projection.get("memory_persistence") != "NONE":
        return {"status": "HOLD", "reason": "COMPETING_MEMORY_STORE_FORBIDDEN"}

    body = {k: v for k, v in projection.items() if k != "projection_digest"}
    if projection.get("projection_digest") != digest(body):
        return {"status": "HOLD", "reason": "CAUSAL_PROJECTION_DIGEST_MISMATCH"}
    if projection.get("status") != "READY":
        return {"status": "HOLD", "reason": str(projection.get("reason") or "CAUSAL_PROJECTION_HOLD")}
    if projection.get("causality_inferred_from_sequence") is not False:
        return {"status": "HOLD", "reason": "SEQUENCE_CAUSALITY_INFERENCE_FORBIDDEN"}
    return {"status": "READY", "reason": "CAUSAL_MEMORY_PROJECTION_VALID"}
