from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Iterable

from macro_evaluation import validate_macro_evaluation

SCHEMA = "lom.macro-closed-loop-binding/1"
AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"

LOW_RISK_TARGETS = {"EVALUATION", "OBSERVABILITY", "TEST_COVERAGE", "DOCUMENTATION"}
MEDIUM_RISK_TARGETS = {"NON_PROD_WORKFLOW", "ROUTING", "PROMPT", "NON_PROD_CODE", "UI_NON_PROD"}
ALLOWED_TARGETS = LOW_RISK_TARGETS | MEDIUM_RISK_TARGETS

VL_ROOT = Path(__file__).resolve().parents[1]


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _load_module(name: str, relative: str):
    if name in sys.modules:
        return sys.modules[name]
    path = VL_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_LOAD_FAILED:{relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _hold(reason: str) -> dict[str, Any]:
    body = {
        "schema": SCHEMA,
        "status": "HOLD",
        "reason": reason,
        "handoffs": [],
        "handoff_count": 0,
        "queue_mutation": "NONE",
        "execution_performed": False,
        "self_apply": "FORBIDDEN",
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
    }
    return {**body, "binding_digest": digest(body)}


def _risk_for_target(target: str) -> str:
    if target in LOW_RISK_TARGETS:
        return "LOW"
    if target in MEDIUM_RISK_TARGETS:
        return "MEDIUM"
    raise ValueError("LEARNING_TARGET_FORBIDDEN")


def _canonical_runtime_gate(
    *,
    candidate_id: str,
    target: str,
    proposed_change: str,
    evidence_ref: str,
    risk: str,
) -> tuple[str, str]:
    runtime = _load_module(
        "lom_closed_loop_self_improvement_runtime",
        "lom-self-improvement-runtime/self_improvement_runtime.py",
    )
    observation = runtime.Observation(
        observation_id=f"macro-observation:{candidate_id}",
        target=target,
        evidence_state="READY",
        evidence_ref=evidence_ref,
        problem=proposed_change,
    )
    candidate = runtime.CandidateImprovement(
        candidate_id=candidate_id,
        target=target,
        proposed_change=proposed_change,
        risk=risk,
        reversible=True,
        production=False,
    )
    return runtime.SelfImprovementRuntime().observe(observation), runtime.SelfImprovementRuntime().stage(candidate)


def compile_closed_loop_handoffs(report: dict[str, Any]) -> dict[str, Any]:
    validation = validate_macro_evaluation(report)
    if validation.get("status") != "READY":
        return _hold(f"MACRO_REPORT_INVALID:{validation.get('reason', 'UNKNOWN')}")

    if report.get("learning_disposition") != "PROPOSE_ONLY":
        return _hold("MACRO_LEARNING_DISPOSITION_MUST_BE_PROPOSE_ONLY")
    if report.get("execution_authority") != EXECUTION_AUTHORITY:
        return _hold("MACRO_EXECUTION_AUTHORITY_WEAKENED")
    if report.get("production_authority") != PRODUCTION_AUTHORITY:
        return _hold("MACRO_PRODUCTION_AUTHORITY_WEAKENED")
    if report.get("protected_main_merge") != PROTECTED_MAIN_MERGE:
        return _hold("MACRO_PROTECTED_MAIN_AUTHORITY_WEAKENED")
    if report.get("self_apply") != "FORBIDDEN":
        return _hold("MACRO_SELF_APPLY_FORBIDDEN")

    evidence_ref = str(report.get("report_digest") or "").strip()
    if not evidence_ref.startswith("sha256:"):
        return _hold("MACRO_REPORT_DIGEST_REQUIRED")

    handoffs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in report.get("learning_candidates") or []:
        if not isinstance(raw, dict):
            return _hold("LEARNING_CANDIDATE_INVALID")
        candidate_id = str(raw.get("candidate_id") or "").strip()
        target = str(raw.get("target") or "").strip()
        proposed_change = str(raw.get("proposed_change") or "").strip()
        pattern_id = str(raw.get("supporting_pattern_id") or "").strip()
        refs = sorted(set(str(x).strip() for x in (raw.get("supporting_evidence_refs") or []) if str(x).strip()))
        traces = sorted(set(str(x).strip() for x in (raw.get("supporting_trace_ids") or []) if str(x).strip()))
        causal_status = str(raw.get("causal_status") or "").strip()
        severity = str(raw.get("severity") or "").strip()

        if not candidate_id or candidate_id in seen:
            return _hold("LEARNING_CANDIDATE_ID_INVALID")
        seen.add(candidate_id)
        if raw.get("disposition") != "PROPOSE_ONLY":
            return _hold("LEARNING_CANDIDATE_NOT_PROPOSE_ONLY")
        if target not in ALLOWED_TARGETS:
            return _hold("LEARNING_TARGET_FORBIDDEN")
        if not proposed_change or not pattern_id or not refs or not traces:
            return _hold("LEARNING_CANDIDATE_EVIDENCE_INCOMPLETE")
        if causal_status not in {"OBSERVATIONAL", "CAUSAL_SUPPORTED"}:
            return _hold("LEARNING_CAUSAL_STATUS_INVALID")
        if severity not in {"LOW", "MEDIUM", "HIGH"}:
            return _hold("LEARNING_SEVERITY_INVALID")

        risk = _risk_for_target(target)
        observe_gate, stage_gate = _canonical_runtime_gate(
            candidate_id=candidate_id,
            target=target,
            proposed_change=proposed_change,
            evidence_ref=evidence_ref,
            risk=risk,
        )
        if observe_gate != "DIAGNOSE":
            return _hold(f"SELF_IMPROVEMENT_OBSERVE_BLOCKED:{observe_gate}")
        if stage_gate != "SANDBOX":
            return _hold(f"SELF_IMPROVEMENT_STAGE_BLOCKED:{stage_gate}")

        handoff_body = {
            "candidate_id": candidate_id,
            "target": target,
            "proposed_change": proposed_change,
            "risk": risk,
            "reversible": True,
            "production": False,
            "supporting_pattern_id": pattern_id,
            "supporting_trace_ids": traces,
            "supporting_evidence_refs": refs,
            "macro_report_ref": evidence_ref,
            "causal_status": causal_status,
            "severity": severity,
            "self_improvement_observe_gate": observe_gate,
            "self_improvement_stage_gate": stage_gate,
            "decision_twin_required": True,
            "decision_twin_execution": "FORBIDDEN",
            "caie_queue_before_decision_twin": "FORBIDDEN",
            "caie_event_draft": {
                "event_id": f"macro-learning:{candidate_id}",
                "event_type": "OBSERVABILITY_ALERT",
                "objective": proposed_change,
                "target": target,
                "risk": risk,
                "reversible": True,
                "production": False,
                "evidence_ref": evidence_ref,
            },
        }
        handoffs.append({**handoff_body, "handoff_digest": digest(handoff_body)})

    body = {
        "schema": SCHEMA,
        "status": "READY",
        "reason": "MACRO_LEARNING_HANDOFFS_READY",
        "macro_report_ref": evidence_ref,
        "handoffs": sorted(handoffs, key=lambda x: x["candidate_id"]),
        "handoff_count": len(handoffs),
        "queue_mutation": "NONE",
        "execution_performed": False,
        "self_apply": "FORBIDDEN",
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
    }
    return {**body, "binding_digest": digest(body)}


def _validate_handoff(handoff: dict[str, Any]) -> str | None:
    if not isinstance(handoff, dict):
        return "HANDOFF_INVALID"
    body = {k: v for k, v in handoff.items() if k != "handoff_digest"}
    if handoff.get("handoff_digest") != digest(body):
        return "HANDOFF_DIGEST_MISMATCH"
    if handoff.get("decision_twin_required") is not True:
        return "DECISION_TWIN_REQUIRED"
    if handoff.get("caie_queue_before_decision_twin") != "FORBIDDEN":
        return "PREMATURE_CAIE_QUEUE_FORBIDDEN"
    if handoff.get("production") is not False:
        return "PRODUCTION_CANDIDATE_FORBIDDEN"
    if handoff.get("target") not in ALLOWED_TARGETS:
        return "LEARNING_TARGET_FORBIDDEN"
    return None


def evaluate_handoff_with_decision_twin(
    handoff: dict[str, Any],
    replay_rows: Iterable[dict[str, Any]],
    *,
    policy_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error = _validate_handoff(handoff)
    if error:
        return {"status": "HOLD", "reason": error, "caie_event": None, "execution_performed": False}

    twin = _load_module(
        "lom_closed_loop_decision_twin",
        "lom-self-improvement-runtime/decision_twin.py",
    )
    candidate = twin.CandidateSpec(
        candidate_id=handoff["candidate_id"],
        target=handoff["target"],
        proposed_change=handoff["proposed_change"],
        risk=handoff["risk"],
        reversible=True,
        production=False,
    )
    try:
        replays = [twin.HistoricalReplay(**dict(row)) for row in replay_rows]
        policy = twin.EvaluationPolicy(**(policy_overrides or {}))
        result = twin.evaluate_counterfactual(candidate, replays, policy=policy)
    except (TypeError, ValueError) as exc:
        return {
            "status": "HOLD",
            "reason": f"DECISION_TWIN_INPUT_INVALID:{type(exc).__name__}",
            "caie_event": None,
            "execution_performed": False,
        }

    if result.get("status") != "SANDBOX_CANDIDATE":
        body = {
            "status": "HOLD",
            "reason": f"DECISION_TWIN_BLOCKED:{result.get('status')}:{result.get('reason')}",
            "decision_twin": result,
            "caie_event": None,
            "execution_performed": False,
            "queue_mutation": "NONE",
            "autonomous_ceiling": AUTONOMOUS_CEILING,
            "production_authority": PRODUCTION_AUTHORITY,
            "protected_main_merge": PROTECTED_MAIN_MERGE,
        }
        return {**body, "evaluation_digest": digest(body)}

    required = {
        "candidate_id": handoff["candidate_id"],
        "target": handoff["target"],
        "next_stage": "LOM_6_7_VALIDATION_SANDBOX",
        "execution_authority": EXECUTION_AUTHORITY,
        "execution_performed": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "authority_widening": "DISABLED",
    }
    for key, expected in required.items():
        if result.get(key) != expected:
            return {
                "status": "HOLD",
                "reason": f"DECISION_TWIN_INVARIANT_MISMATCH:{key}",
                "caie_event": None,
                "execution_performed": False,
            }
    fp = str(result.get("decision_twin_fingerprint") or "")
    if len(fp) != 64:
        return {"status": "HOLD", "reason": "DECISION_TWIN_FINGERPRINT_REQUIRED", "caie_event": None, "execution_performed": False}

    body = {
        "status": "READY_FOR_CAIE",
        "reason": "DECISION_TWIN_SUPPORTED",
        "decision_twin": result,
        "caie_event": dict(handoff["caie_event_draft"]),
        "execution_performed": False,
        "queue_mutation": "NONE",
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
    }
    return {**body, "evaluation_digest": digest(body)}


def queue_validated_handoff(
    router: Any,
    evaluated: dict[str, Any],
    *,
    builder_id: str,
    validator_id: str,
    certifier_id: str,
    max_remediation_attempts: int = 2,
) -> dict[str, Any]:
    if not isinstance(evaluated, dict):
        return {"status": "HOLD", "reason": "EVALUATED_HANDOFF_INVALID"}
    stored = evaluated.get("evaluation_digest")
    body = {k: v for k, v in evaluated.items() if k != "evaluation_digest"}
    if stored != digest(body):
        return {"status": "HOLD", "reason": "EVALUATED_HANDOFF_DIGEST_MISMATCH"}
    if evaluated.get("status") != "READY_FOR_CAIE":
        return {"status": "HOLD", "reason": "DECISION_TWIN_SUPPORT_REQUIRED"}
    if evaluated.get("execution_performed") is not False or evaluated.get("queue_mutation") != "NONE":
        return {"status": "HOLD", "reason": "PRE_QUEUE_STATE_INVALID"}
    event = evaluated.get("caie_event")
    if not isinstance(event, dict) or event.get("production") is not False:
        return {"status": "HOLD", "reason": "CAIE_EVENT_INVALID"}

    decision = router.ingest(
        SimpleNamespace(**event),
        builder_id=builder_id,
        validator_id=validator_id,
        certifier_id=certifier_id,
        max_remediation_attempts=max_remediation_attempts,
    )
    raw = asdict(decision) if is_dataclass(decision) else {
        "disposition": getattr(decision, "disposition", None),
        "reason": getattr(decision, "reason", None),
        "task_id": getattr(decision, "task_id", None),
    }
    return {
        "status": "QUEUED" if raw.get("disposition") == "ACCEPT" else raw.get("disposition", "HOLD"),
        "reason": raw.get("reason"),
        "task_id": raw.get("task_id"),
        "queue_mutation": "DURABLE_NON_PRODUCTION_TASK" if raw.get("disposition") == "ACCEPT" else "NONE",
        "execution_performed": False,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
    }
