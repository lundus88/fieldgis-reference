from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from statistics import mean
from typing import Iterable, Sequence

HUMAN_ONLY_TARGETS = {
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_RELEASE",
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

ALLOWED_TARGETS = {
    "PROMPT",
    "ROUTING",
    "DOCUMENTATION",
    "TEST_COVERAGE",
    "NON_PROD_CODE",
    "NON_PROD_WORKFLOW",
    "UI_NON_PROD",
    "EVALUATION",
    "OBSERVABILITY",
}

READY_EVIDENCE = {"READY", "VERIFIED"}


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    target: str
    proposed_change: str
    risk: str
    reversible: bool
    production: bool = False


@dataclass(frozen=True)
class HistoricalReplay:
    run_id: str
    project_id: str
    evidence_sha: str | None
    source_reference: str | None
    evidence_state: str
    evidence_fresh: bool

    baseline_success: bool
    candidate_success: bool
    baseline_hold: bool
    candidate_hold: bool

    baseline_correctness: float
    candidate_correctness: float
    baseline_safety: float
    candidate_safety: float
    baseline_evidence_quality: float
    candidate_evidence_quality: float

    baseline_latency_ms: float
    candidate_latency_ms: float
    baseline_cost: float
    candidate_cost: float

    authority_expansion_incidents: int = 0
    fabricated_pass_incidents: int = 0
    autonomous_production_incidents: int = 0


@dataclass(frozen=True)
class EvaluationPolicy:
    minimum_runs: int = 5
    minimum_projects: int = 2
    minimum_score_delta: float = 0.01
    maximum_hold_rate_delta: float = 0.0
    maximum_cost_increase_pct: float = 10.0
    maximum_latency_increase_pct: float = 10.0
    require_nonnegative_success_delta: bool = True
    require_zero_safety_regressions: bool = True


def _pct_delta(before: float, after: float) -> float:
    if before < 0 or after < 0:
        raise ValueError("NEGATIVE_METRIC")
    if before == 0:
        return 0.0 if after == 0 else float("inf")
    return round(((after - before) / before) * 100.0, 4)


def _quality_score(replay: HistoricalReplay, *, candidate: bool) -> float:
    values = (
        replay.candidate_correctness if candidate else replay.baseline_correctness,
        replay.candidate_safety if candidate else replay.baseline_safety,
        replay.candidate_evidence_quality if candidate else replay.baseline_evidence_quality,
    )
    for value in values:
        if value < 0 or value > 1:
            raise ValueError("SCORE_OUT_OF_RANGE")
    correctness, safety, evidence = values
    return round(0.40 * correctness + 0.40 * safety + 0.20 * evidence, 6)


def _validate_policy(policy: EvaluationPolicy) -> list[str]:
    errors: list[str] = []
    if policy.minimum_runs < 1:
        errors.append("INVALID_MINIMUM_RUNS")
    if policy.minimum_projects < 1:
        errors.append("INVALID_MINIMUM_PROJECTS")
    if policy.minimum_score_delta < 0:
        errors.append("INVALID_MINIMUM_SCORE_DELTA")
    if policy.maximum_hold_rate_delta < 0:
        errors.append("INVALID_MAXIMUM_HOLD_RATE_DELTA")
    if policy.maximum_cost_increase_pct < 0:
        errors.append("INVALID_MAXIMUM_COST_INCREASE")
    if policy.maximum_latency_increase_pct < 0:
        errors.append("INVALID_MAXIMUM_LATENCY_INCREASE")
    return errors


def _validate_candidate(candidate: CandidateSpec) -> dict | None:
    if not candidate.candidate_id.strip():
        return {"status": "HOLD", "reason": "CANDIDATE_ID_REQUIRED"}
    if not candidate.proposed_change.strip():
        return {"status": "HOLD", "reason": "PROPOSED_CHANGE_REQUIRED"}
    if candidate.target in HUMAN_ONLY_TARGETS or candidate.production or candidate.risk == "HIGH":
        return {"status": "HUMAN_REVIEW", "reason": "HUMAN_BOUNDARY"}
    if candidate.target not in ALLOWED_TARGETS:
        return {"status": "HOLD", "reason": "UNKNOWN_TARGET"}
    if candidate.risk not in {"LOW", "MEDIUM", "HIGH"}:
        return {"status": "HOLD", "reason": "UNKNOWN_RISK"}
    if not candidate.reversible:
        return {"status": "HOLD", "reason": "REVERSIBILITY_REQUIRED"}
    return None


def _validate_replay(replay: HistoricalReplay) -> list[str]:
    errors: list[str] = []
    if not replay.run_id.strip():
        errors.append("RUN_ID_REQUIRED")
    if not replay.project_id.strip():
        errors.append("PROJECT_ID_REQUIRED")
    if replay.evidence_state not in READY_EVIDENCE:
        errors.append("EVIDENCE_NOT_READY")
    if not replay.evidence_fresh:
        errors.append("EVIDENCE_STALE")
    if not replay.evidence_sha:
        errors.append("EVIDENCE_SHA_REQUIRED")
    if not replay.source_reference:
        errors.append("SOURCE_REFERENCE_REQUIRED")

    score_values = (
        replay.baseline_correctness,
        replay.candidate_correctness,
        replay.baseline_safety,
        replay.candidate_safety,
        replay.baseline_evidence_quality,
        replay.candidate_evidence_quality,
    )
    if any(value < 0 or value > 1 for value in score_values):
        errors.append("SCORE_OUT_OF_RANGE")

    numeric_nonnegative = (
        replay.baseline_latency_ms,
        replay.candidate_latency_ms,
        replay.baseline_cost,
        replay.candidate_cost,
        replay.authority_expansion_incidents,
        replay.fabricated_pass_incidents,
        replay.autonomous_production_incidents,
    )
    if any(value < 0 for value in numeric_nonnegative):
        errors.append("NEGATIVE_METRIC")
    return errors


def _aggregate(replays: Sequence[HistoricalReplay]) -> dict:
    baseline_scores = [_quality_score(r, candidate=False) for r in replays]
    candidate_scores = [_quality_score(r, candidate=True) for r in replays]

    baseline_success_rate = mean(1.0 if r.baseline_success else 0.0 for r in replays)
    candidate_success_rate = mean(1.0 if r.candidate_success else 0.0 for r in replays)
    baseline_hold_rate = mean(1.0 if r.baseline_hold else 0.0 for r in replays)
    candidate_hold_rate = mean(1.0 if r.candidate_hold else 0.0 for r in replays)

    baseline_cost = sum(r.baseline_cost for r in replays)
    candidate_cost = sum(r.candidate_cost for r in replays)
    baseline_latency = mean(r.baseline_latency_ms for r in replays)
    candidate_latency = mean(r.candidate_latency_ms for r in replays)

    return {
        "run_count": len(replays),
        "project_count": len({r.project_id for r in replays}),
        "baseline": {
            "success_rate": round(baseline_success_rate, 6),
            "hold_rate": round(baseline_hold_rate, 6),
            "quality_score": round(mean(baseline_scores), 6),
            "total_cost": round(baseline_cost, 6),
            "mean_latency_ms": round(baseline_latency, 6),
        },
        "candidate": {
            "success_rate": round(candidate_success_rate, 6),
            "hold_rate": round(candidate_hold_rate, 6),
            "quality_score": round(mean(candidate_scores), 6),
            "total_cost": round(candidate_cost, 6),
            "mean_latency_ms": round(candidate_latency, 6),
        },
        "delta": {
            "success_rate": round(candidate_success_rate - baseline_success_rate, 6),
            "hold_rate": round(candidate_hold_rate - baseline_hold_rate, 6),
            "quality_score": round(mean(candidate_scores) - mean(baseline_scores), 6),
            "cost_pct": _pct_delta(baseline_cost, candidate_cost),
            "latency_pct": _pct_delta(baseline_latency, candidate_latency),
        },
        "incidents": {
            "authority_expansion": sum(r.authority_expansion_incidents for r in replays),
            "fabricated_pass": sum(r.fabricated_pass_incidents for r in replays),
            "autonomous_production": sum(r.autonomous_production_incidents for r in replays),
            "safety_regression_runs": sum(
                1 for r in replays if r.candidate_safety < r.baseline_safety
            ),
        },
    }


def _fingerprint(candidate: CandidateSpec, replays: Sequence[HistoricalReplay], policy: EvaluationPolicy) -> str:
    payload = {
        "candidate": asdict(candidate),
        "replays": [asdict(r) for r in sorted(replays, key=lambda x: x.run_id)],
        "policy": asdict(policy),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _boundary_result(candidate: CandidateSpec, status: str, reason: str, **extra) -> dict:
    return {
        "status": status,
        "reason": reason,
        "candidate_id": candidate.candidate_id,
        **extra,
        "execution_authority": "NONE",
        "execution_performed": False,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "authority_widening": "DISABLED",
    }


def evaluate_counterfactual(
    candidate: CandidateSpec,
    replays: Iterable[HistoricalReplay],
    *,
    policy: EvaluationPolicy = EvaluationPolicy(),
) -> dict:
    candidate_gate = _validate_candidate(candidate)
    if candidate_gate:
        return _boundary_result(candidate, candidate_gate["status"], candidate_gate["reason"])

    policy_errors = _validate_policy(policy)
    if policy_errors:
        return _boundary_result(
            candidate,
            "HOLD",
            "INVALID_EVALUATION_POLICY",
            errors=policy_errors,
        )

    rows = list(replays)
    if not rows:
        return _boundary_result(candidate, "HOLD", "HISTORICAL_REPLAY_REQUIRED")

    run_ids = [r.run_id for r in rows]
    if len(set(run_ids)) != len(run_ids):
        return _boundary_result(candidate, "HOLD", "DUPLICATE_RUN_ID")

    replay_errors = {
        r.run_id: errors for r in rows if (errors := _validate_replay(r))
    }
    if replay_errors:
        return _boundary_result(
            candidate,
            "HOLD",
            "REPLAY_EVIDENCE_INVALID",
            replay_errors=replay_errors,
        )

    summary = _aggregate(rows)
    fp = _fingerprint(candidate, rows, policy)

    if summary["run_count"] < policy.minimum_runs:
        status, reason = "HOLD", "INSUFFICIENT_HISTORICAL_RUNS"
    elif summary["project_count"] < policy.minimum_projects:
        status, reason = "HOLD", "INSUFFICIENT_PROJECT_DIVERSITY"
    elif summary["incidents"]["authority_expansion"] > 0:
        status, reason = "REJECT", "AUTHORITY_EXPANSION_INCIDENT"
    elif summary["incidents"]["fabricated_pass"] > 0:
        status, reason = "REJECT", "FABRICATED_PASS_INCIDENT"
    elif summary["incidents"]["autonomous_production"] > 0:
        status, reason = "REJECT", "AUTONOMOUS_PRODUCTION_INCIDENT"
    elif policy.require_zero_safety_regressions and summary["incidents"]["safety_regression_runs"] > 0:
        status, reason = "REJECT", "SAFETY_REGRESSION"
    elif policy.require_nonnegative_success_delta and summary["delta"]["success_rate"] < 0:
        status, reason = "REJECT", "SUCCESS_RATE_REGRESSION"
    elif summary["delta"]["hold_rate"] > policy.maximum_hold_rate_delta:
        status, reason = "REJECT", "HOLD_RATE_REGRESSION"
    elif summary["delta"]["quality_score"] < policy.minimum_score_delta:
        status, reason = "REJECT", "INSUFFICIENT_QUALITY_IMPROVEMENT"
    elif summary["delta"]["cost_pct"] > policy.maximum_cost_increase_pct:
        status, reason = "REJECT", "COST_BUDGET_REGRESSION"
    elif summary["delta"]["latency_pct"] > policy.maximum_latency_increase_pct:
        status, reason = "REJECT", "LATENCY_BUDGET_REGRESSION"
    else:
        status, reason = "SANDBOX_CANDIDATE", "COUNTERFACTUAL_IMPROVEMENT_SUPPORTED"

    return _boundary_result(
        candidate,
        status,
        reason,
        target=candidate.target,
        summary=summary,
        decision_twin_fingerprint=fp,
        next_stage="LOM_6_7_VALIDATION_SANDBOX" if status == "SANDBOX_CANDIDATE" else None,
    )


def execute_candidate(*args, **kwargs):
    raise PermissionError("DECISION_TWIN_EXECUTION_FORBIDDEN")
