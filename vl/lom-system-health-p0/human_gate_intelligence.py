from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

HUMAN_AUTHORITIES = {"HUMAN_APPROVAL"}
AUTO_AUTHORITIES = {"AUTO", "AUTO_WITHIN_SCOPE", "AUTO_SEPARATE_ROLE"}
ALLOWED_OUTCOMES = {"SUCCESS", "FAIL", "HOLD", "SKIP"}

HARD_HUMAN_ACTIONS = {
    "MERGE_PROTECTED_MAIN",
    "PRODUCTION_DEPLOY",
    "PRODUCTION_DATA_MUTATION",
    "PRODUCTION_AUTHORITY_CHANGE",
    "FINANCIAL_OR_CONTRACTUAL_COMMITMENT",
}


@dataclass(frozen=True)
class InterventionEvent:
    event_id: str
    action: str
    environment: str
    human_intervention: bool
    evidence_complete: bool
    outcome: str
    source_reference: str
    observed_at_epoch: int


def load_authority_matrix(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_authority_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    if matrix.get("version") != "1.0":
        return {"status": "HOLD", "reason": "AUTHORITY_MATRIX_VERSION_INVALID"}
    if matrix.get("default_decision") != "DENY_OR_HOLD":
        return {"status": "HOLD", "reason": "AUTHORITY_DEFAULT_MUST_FAIL_CLOSED"}

    rules = matrix.get("rules")
    if not isinstance(rules, list) or not rules:
        return {"status": "HOLD", "reason": "AUTHORITY_RULES_REQUIRED"}

    by_action: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        action = rule.get("action")
        authority = rule.get("authority")
        environment = rule.get("environment")
        if not action or authority not in HUMAN_AUTHORITIES | AUTO_AUTHORITIES:
            return {"status": "HOLD", "reason": "AUTHORITY_RULE_INVALID"}
        if environment not in {"NON_PRODUCTION", "PRODUCTION", "ANY"}:
            return {"status": "HOLD", "reason": "AUTHORITY_ENVIRONMENT_INVALID"}
        if rule.get("evidence_required") is not True:
            return {"status": "HOLD", "reason": "EVIDENCE_REQUIREMENT_WEAKENED"}
        by_action.setdefault(action, []).append(rule)

    for action in HARD_HUMAN_ACTIONS:
        rules_for_action = by_action.get(action, [])
        if not rules_for_action or any(rule.get("authority") != "HUMAN_APPROVAL" for rule in rules_for_action):
            return {"status": "HOLD", "reason": "HARD_HUMAN_GATE_WEAKENED", "action": action}

    invariants = matrix.get("invariants") or {}
    required_invariants = {
        "production_approval_human_only": True,
        "builder_self_certification_allowed": False,
        "delegation_may_widen_scope": False,
        "unknown_authority_allowed": False,
    }
    for key, value in required_invariants.items():
        if invariants.get(key) is not value:
            return {"status": "HOLD", "reason": "AUTHORITY_INVARIANT_WEAKENED", "invariant": key}

    return {
        "status": "READY",
        "reason": "AUTHORITY_MATRIX_VALID",
        "rule_count": len(rules),
        "hard_human_actions": sorted(HARD_HUMAN_ACTIONS),
    }


def _match_rule(matrix: dict[str, Any], action: str, environment: str) -> dict[str, Any] | None:
    matches = []
    for rule in matrix.get("rules") or []:
        if rule.get("action") != action:
            continue
        if rule.get("environment") in {environment, "ANY"}:
            matches.append(rule)
    if len(matches) != 1:
        return None
    return matches[0]


def classify_gate(matrix: dict[str, Any], action: str, environment: str) -> dict[str, Any]:
    validation = validate_authority_matrix(matrix)
    if validation["status"] != "READY":
        return validation

    rule = _match_rule(matrix, action, environment)
    if rule is None:
        return {
            "status": "HOLD",
            "reason": "UNKNOWN_OR_AMBIGUOUS_AUTHORITY",
            "action": action,
            "environment": environment,
        }

    authority = rule["authority"]
    mandatory_human = authority == "HUMAN_APPROVAL"
    automation_eligible = authority in AUTO_AUTHORITIES

    if action in HARD_HUMAN_ACTIONS and not mandatory_human:
        return {"status": "HOLD", "reason": "HARD_HUMAN_GATE_WEAKENED", "action": action}

    return {
        "status": "CLASSIFIED",
        "action": action,
        "environment": environment,
        "authority": authority,
        "mandatory_human": mandatory_human,
        "automation_eligible": automation_eligible,
        "evidence_required": True,
        "authority_change": "DISABLED",
    }


def measure_intervention_friction(
    matrix: dict[str, Any],
    events: Iterable[InterventionEvent],
    *,
    now_epoch: int,
    max_age_seconds: int,
    target_avoidable_human_rate_pct: float = 5.0,
) -> dict[str, Any]:
    validation = validate_authority_matrix(matrix)
    if validation["status"] != "READY":
        return {
            "schema": "lom.human-gate-minimization/1",
            "status": "HOLD",
            "reason": validation["reason"],
            "authority_change": "DISABLED",
        }

    if now_epoch <= 0 or max_age_seconds <= 0 or not 0 <= target_avoidable_human_rate_pct <= 100:
        return {
            "schema": "lom.human-gate-minimization/1",
            "status": "HOLD",
            "reason": "MEASUREMENT_INPUT_INVALID",
            "authority_change": "DISABLED",
        }

    items = list(events)
    seen_ids: set[str] = set()
    violations: list[dict[str, Any]] = []
    eligible_events: list[dict[str, Any]] = []
    mandatory_events: list[dict[str, Any]] = []
    friction_candidates: list[dict[str, Any]] = []

    total_human_touches = 0

    for event in items:
        if not event.event_id or event.event_id in seen_ids:
            violations.append({"event_id": event.event_id or None, "reason": "EVENT_ID_MISSING_OR_DUPLICATE"})
            continue
        seen_ids.add(event.event_id)

        if event.outcome not in ALLOWED_OUTCOMES or not event.source_reference:
            violations.append({"event_id": event.event_id, "reason": "EVENT_EVIDENCE_INVALID"})
            continue
        if event.observed_at_epoch <= 0 or event.observed_at_epoch > now_epoch:
            violations.append({"event_id": event.event_id, "reason": "EVENT_TIME_INVALID"})
            continue
        if now_epoch - event.observed_at_epoch > max_age_seconds:
            violations.append({"event_id": event.event_id, "reason": "EVENT_STALE"})
            continue

        gate = classify_gate(matrix, event.action, event.environment)
        if gate.get("status") != "CLASSIFIED":
            violations.append({"event_id": event.event_id, "reason": gate.get("reason", "GATE_CLASSIFICATION_FAILED")})
            continue

        if event.human_intervention:
            total_human_touches += 1

        row = {
            "event_id": event.event_id,
            "action": event.action,
            "environment": event.environment,
            "authority": gate["authority"],
            "human_intervention": event.human_intervention,
            "evidence_complete": event.evidence_complete,
            "outcome": event.outcome,
            "source_reference": event.source_reference,
        }

        if gate["mandatory_human"]:
            mandatory_events.append(row)
            if not event.human_intervention:
                violations.append({"event_id": event.event_id, "reason": "MANDATORY_HUMAN_GATE_NOT_OBSERVED"})
            continue

        eligible_events.append(row)

        if event.human_intervention:
            reason = "MANUAL_FRICTION_WITH_COMPLETE_EVIDENCE" if event.evidence_complete else "MANUAL_FRICTION_EVIDENCE_INCOMPLETE"
            friction_candidates.append({
                **row,
                "reason": reason,
                "recommended_action": (
                    "Investigate workflow friction and pre-validation; preserve current authority matrix."
                    if event.evidence_complete
                    else "Complete evidence automation before considering any workflow simplification."
                ),
                "automatic_gate_removal": "FORBIDDEN",
            })

    eligible_count = len(eligible_events)
    avoidable_human_count = sum(1 for item in eligible_events if item["human_intervention"])
    avoidable_rate = round((avoidable_human_count / eligible_count * 100.0), 4) if eligible_count else 0.0
    total_rate = round((total_human_touches / len(items) * 100.0), 4) if items else 0.0

    status = "HEALTHY"
    reason = "AVOIDABLE_HUMAN_RATE_WITHIN_TARGET"
    if violations:
        status = "HOLD"
        reason = "AUTHORITY_OR_EVIDENCE_VIOLATION"
    elif avoidable_rate > target_avoidable_human_rate_pct:
        status = "DEGRADED"
        reason = "AVOIDABLE_HUMAN_RATE_ABOVE_TARGET"

    return {
        "schema": "lom.human-gate-minimization/1",
        "status": status,
        "reason": reason,
        "metrics": {
            "event_count": len(items),
            "mandatory_human_event_count": len(mandatory_events),
            "automation_eligible_event_count": eligible_count,
            "avoidable_human_intervention_count": avoidable_human_count,
            "avoidable_human_intervention_rate_pct": avoidable_rate,
            "target_avoidable_human_rate_pct": target_avoidable_human_rate_pct,
            "total_human_touch_rate_pct": total_rate,
        },
        "mandatory_human_events": mandatory_events,
        "friction_candidates": sorted(friction_candidates, key=lambda item: item["event_id"]),
        "violations": violations,
        "autonomous_ceiling": "PREPARE_PR",
        "authority_change": "DISABLED",
        "automatic_gate_removal": "FORBIDDEN",
        "protected_main_merge": "HUMAN_ONLY",
        "production_authority": "HUMAN_ONLY",
        "financial_legal_customer_commitments": "HUMAN_ONLY",
    }


def build_friction_improvement_backlog(measurement: dict[str, Any]) -> dict[str, Any]:
    if measurement.get("schema") != "lom.human-gate-minimization/1":
        return {"status": "HOLD", "reason": "MEASUREMENT_SCHEMA_INVALID"}
    if measurement.get("status") == "HOLD":
        return {
            "status": "HOLD",
            "reason": "MEASUREMENT_MUST_BE_TRUSTWORTHY_FIRST",
            "items": [],
            "authority_change": "DISABLED",
        }

    items = []
    for candidate in measurement.get("friction_candidates") or []:
        if candidate.get("authority") == "HUMAN_APPROVAL" or candidate.get("action") in HARD_HUMAN_ACTIONS:
            return {
                "status": "HOLD",
                "reason": "MANDATORY_GATE_ENTERED_FRICTION_BACKLOG",
                "items": [],
                "authority_change": "DISABLED",
            }
        items.append({
            "event_id": candidate["event_id"],
            "action": candidate["action"],
            "environment": candidate["environment"],
            "recommendation": candidate["recommended_action"],
            "allowed_ceiling": "PREPARE_PR",
            "authority_matrix_change": "FORBIDDEN",
            "production_execution": "DISABLED",
        })

    return {
        "status": "READY",
        "reason": "FRICTION_BACKLOG_READY",
        "items": items,
        "target": "Reduce avoidable human intervention without weakening consequential human authority.",
        "autonomous_ceiling": "PREPARE_PR",
        "authority_change": "DISABLED",
    }
