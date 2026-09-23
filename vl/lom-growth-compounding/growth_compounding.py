from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

AUTONOMOUS_CEILING = "PREPARE_PR"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"
EXECUTION_AUTHORITY = "NONE"

ALLOWED_CAIE_TARGETS = {
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

MANDATORY_HUMAN_BOUNDARIES = {
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


@dataclass(frozen=True)
class GrowthTelemetry:
    objective_id: str
    project_id: str
    evidence_ref: str
    evidence_fresh: bool

    # Speed
    time_to_value_minutes: float
    target_time_to_value_minutes: float
    cycle_time_minutes: float
    target_cycle_time_minutes: float

    # Automation
    automation_eligible_steps: int
    automated_eligible_steps: int
    avoidable_human_touches: int

    # Distribution
    qualified_visitors: int
    activated_users: int
    target_activation_rate: float

    # Learning
    feedback_to_verified_change_hours: float
    target_learning_latency_hours: float

    # Compounding
    completed_customers: int
    repeat_or_referral_customers: int
    target_repeat_referral_rate: float

    # Safety / quality
    evidence_gap_count: int = 0
    critical_incident_count: int = 0
    defect_rate: float = 0.0
    max_defect_rate: float = 0.0

    # Governance context
    proposed_target: str = "NON_PROD_WORKFLOW"
    reversible: bool = True
    production: bool = False
    touches_mandatory_human_boundary: Optional[str] = None


def _finite_nonnegative(value: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and value >= 0


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _base(status: str, reason: str) -> dict:
    return {
        "status": status,
        "reason": reason,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "execution_authority": EXECUTION_AUTHORITY,
        "execution_performed": False,
        "self_approval": "FORBIDDEN",
    }


def evaluate_growth_bottleneck(t: GrowthTelemetry) -> dict:
    if not t.objective_id or not t.project_id:
        return _base("HOLD", "OBJECTIVE_AND_PROJECT_REQUIRED")
    if not t.evidence_ref or "://" not in t.evidence_ref and not t.evidence_ref.startswith(("urn:", "sha256:")):
        return _base("HOLD", "EVIDENCE_REFERENCE_REQUIRED")
    if not t.evidence_fresh:
        return _base("HOLD", "EVIDENCE_STALE")
    if t.production:
        return _base("HUMAN_REVIEW", "PRODUCTION_BOUNDARY")
    if not t.reversible:
        return _base("HUMAN_REVIEW", "REVERSIBILITY_REQUIRED")
    if t.proposed_target in MANDATORY_HUMAN_BOUNDARIES:
        return _base("HUMAN_REVIEW", "MANDATORY_HUMAN_TARGET")
    if t.proposed_target not in ALLOWED_CAIE_TARGETS:
        return _base("HOLD", "UNKNOWN_CAIE_TARGET")

    numeric_values = (
        t.time_to_value_minutes,
        t.target_time_to_value_minutes,
        t.cycle_time_minutes,
        t.target_cycle_time_minutes,
        t.target_activation_rate,
        t.feedback_to_verified_change_hours,
        t.target_learning_latency_hours,
        t.target_repeat_referral_rate,
        t.defect_rate,
        t.max_defect_rate,
    )
    if not all(_finite_nonnegative(v) for v in numeric_values):
        return _base("HOLD", "INVALID_NUMERIC_EVIDENCE")

    integer_values = (
        t.automation_eligible_steps,
        t.automated_eligible_steps,
        t.avoidable_human_touches,
        t.qualified_visitors,
        t.activated_users,
        t.completed_customers,
        t.repeat_or_referral_customers,
        t.evidence_gap_count,
        t.critical_incident_count,
    )
    if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in integer_values):
        return _base("HOLD", "INVALID_COUNTER_EVIDENCE")

    if t.automated_eligible_steps > t.automation_eligible_steps:
        return _base("HOLD", "AUTOMATION_COUNT_CONTRADICTION")
    if t.activated_users > t.qualified_visitors:
        return _base("HOLD", "ACTIVATION_COUNT_CONTRADICTION")
    if t.repeat_or_referral_customers > t.completed_customers:
        return _base("HOLD", "COMPOUNDING_COUNT_CONTRADICTION")
    if t.target_activation_rate > 1 or t.target_repeat_referral_rate > 1 or t.defect_rate > 1 or t.max_defect_rate > 1:
        return _base("HOLD", "RATE_OUT_OF_RANGE")
    if t.evidence_gap_count > 0:
        return _base("HOLD", "EVIDENCE_GAPS_PRESENT")
    if t.critical_incident_count > 0:
        return _base("HUMAN_REVIEW", "CRITICAL_INCIDENT_PRESENT")
    if t.touches_mandatory_human_boundary:
        if t.touches_mandatory_human_boundary not in MANDATORY_HUMAN_BOUNDARIES:
            return _base("HOLD", "UNKNOWN_HUMAN_BOUNDARY")
        return _base("HUMAN_REVIEW", "MANDATORY_HUMAN_BOUNDARY")

    # Quality always dominates acceleration.
    if t.defect_rate > t.max_defect_rate:
        out = _base("CANDIDATE", "QUALITY_BOTTLENECK")
        out.update({
            "lever": "LEARNING",
            "bottleneck": "DEFECT_RATE",
            "recommended_experiment": "Improve deterministic validation/evaluation before increasing speed or automation.",
            "success_metric": "defect_rate",
            "target_value": t.max_defect_rate,
            "caie_target": "EVALUATION",
            "rollback_required": True,
            "evidence_ref": t.evidence_ref,
        })
        return out

    candidates = []

    if t.target_time_to_value_minutes > 0 and t.time_to_value_minutes > t.target_time_to_value_minutes:
        severity = t.time_to_value_minutes / t.target_time_to_value_minutes
        candidates.append((severity, "SPEED", "TIME_TO_VALUE", "NON_PROD_WORKFLOW",
                           "Delete or simplify the highest-latency pre-value step; test one reversible workflow reduction.",
                           "time_to_value_minutes", t.target_time_to_value_minutes))

    if t.target_cycle_time_minutes > 0 and t.cycle_time_minutes > t.target_cycle_time_minutes:
        severity = t.cycle_time_minutes / t.target_cycle_time_minutes
        candidates.append((severity, "SPEED", "CYCLE_TIME", "NON_PROD_WORKFLOW",
                           "Identify the longest bounded workflow wait/queue and remove or parallelize only that bottleneck.",
                           "cycle_time_minutes", t.target_cycle_time_minutes))

    if t.automation_eligible_steps > 0:
        automation_rate = t.automated_eligible_steps / t.automation_eligible_steps
        if automation_rate < 1.0 or t.avoidable_human_touches > 0:
            # Cap severity so a pure automation metric cannot overwhelm very poor user-value latency.
            severity = 1.0 + min(1.0, (1.0 - automation_rate) + (t.avoidable_human_touches / max(1, t.automation_eligible_steps)))
            candidates.append((severity, "AUTOMATION", "ELIGIBLE_MANUAL_FRICTION", "NON_PROD_WORKFLOW",
                               "Automate one already-eligible repetitive step while preserving every mandatory human gate.",
                               "automation_rate", 1.0))

    activation_rate = _ratio(t.activated_users, t.qualified_visitors)
    if activation_rate is not None and activation_rate < t.target_activation_rate:
        severity = (t.target_activation_rate / max(activation_rate, 1e-9)) if t.target_activation_rate > 0 else 1.0
        candidates.append((severity, "DISTRIBUTION", "ACTIVATION_RATE", "UI_NON_PROD",
                           "Run one evidence-bound activation experiment that shortens qualified-user time-to-first-value; do not fabricate demand.",
                           "activation_rate", t.target_activation_rate))

    if t.target_learning_latency_hours > 0 and t.feedback_to_verified_change_hours > t.target_learning_latency_hours:
        severity = t.feedback_to_verified_change_hours / t.target_learning_latency_hours
        candidates.append((severity, "LEARNING", "LEARNING_LATENCY", "OBSERVABILITY",
                           "Shorten the evidence-to-verified-change loop by improving telemetry routing, triage, or deterministic evaluation.",
                           "feedback_to_verified_change_hours", t.target_learning_latency_hours))

    rr_rate = _ratio(t.repeat_or_referral_customers, t.completed_customers)
    if rr_rate is not None and rr_rate < t.target_repeat_referral_rate:
        severity = (t.target_repeat_referral_rate / max(rr_rate, 1e-9)) if t.target_repeat_referral_rate > 0 else 1.0
        candidates.append((severity, "COMPOUNDING", "REPEAT_REFERRAL_RATE", "NON_PROD_WORKFLOW",
                           "Test one reversible post-delivery loop that increases repeat/referral or reusable customer value without changing commitments.",
                           "repeat_referral_rate", t.target_repeat_referral_rate))

    if not candidates:
        out = _base("NO_ACTION", "MEASURED_GROWTH_LEVERS_WITHIN_TARGET")
        out["evidence_ref"] = t.evidence_ref
        return out

    # Highest relative gap wins; deterministic tie-break keeps tests/reviews stable.
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    severity, lever, bottleneck, caie_target, experiment, success_metric, target_value = candidates[0]
    if caie_target not in ALLOWED_CAIE_TARGETS:
        return _base("HOLD", "INTERNAL_TARGET_MAPPING_INVALID")

    out = _base("CANDIDATE", "HIGHEST_EVIDENCE_GROWTH_BOTTLENECK")
    out.update({
        "lever": lever,
        "bottleneck": bottleneck,
        "relative_gap": round(float(severity), 6),
        "recommended_experiment": experiment,
        "success_metric": success_metric,
        "target_value": target_value,
        "caie_target": caie_target,
        "rollback_required": True,
        "evidence_ref": t.evidence_ref,
        "candidate_handoff": "CAIE",
    })
    return out
