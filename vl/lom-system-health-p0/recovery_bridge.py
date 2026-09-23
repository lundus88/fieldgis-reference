from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SAFE_PREPARE_RECIPES = {
    "PREVIEW_DRIFT": ("PREPARE_PREVIEW_REFRESH", "LOW"),
    "CI_NOT_EXACT_MAIN": ("PREPARE_EXACT_MAIN_CI_REFRESH", "LOW"),
    "CI_FAILURE": ("PREPARE_CI_REMEDIATION_PR", "LOW"),
    "RUNTIME_DEGRADED": ("PREPARE_RUNTIME_DIAGNOSTIC_PR", "LOW"),
    "REGRESSION_STALE": ("PREPARE_REGRESSION_EVIDENCE_REFRESH", "LOW"),
    "REQUIRED_JOURNEY_MISSING": ("PREPARE_JOURNEY_BINDING_PR", "LOW"),
    "NONCRITICAL_JOURNEY_FAILED": ("PREPARE_NONCRITICAL_REMEDIATION_PR", "LOW"),
}

HUMAN_REVIEW_REASONS = {
    "PRODUCTION_DRIFT",
    "RUNTIME_FAILURE",
    "CRITICAL_JOURNEY_FAILED",
}

HOLD_REASONS = {
    "DATABASE_DRIFT",
    "DATABASE_EVIDENCE_MISSING",
    "OBSERVATION_STALE",
    "CI_EVIDENCE_UNKNOWN",
    "RUNTIME_EVIDENCE_UNKNOWN",
    "REGRESSION_NOT_EXACT_MAIN",
    "CRITICAL_JOURNEY_SKIPPED",
    "HEALTH_ASSESSMENT_MISSING",
    "REGRESSION_SENTINEL_MISSING",
}


@dataclass(frozen=True)
class RecoveryCandidate:
    project_id: str
    reason: str
    evidence_sha: str
    source_reference: str
    evidence_fresh: bool
    production: bool = False


def _load_planner():
    path = ROOT / "lom-6-6-governed-remediation-planner" / "planner.py"
    spec = importlib.util.spec_from_file_location("lom66_remediation_planner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("REMEDIATION_PLANNER_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def classify_candidate(candidate: RecoveryCandidate) -> dict[str, Any]:
    if not candidate.project_id or not candidate.reason:
        return {"status": "HOLD", "reason": "RECOVERY_IDENTITY_REQUIRED"}

    if candidate.production or candidate.reason in HUMAN_REVIEW_REASONS:
        return {
            "status": "HUMAN_REVIEW",
            "reason": "CONSEQUENTIAL_RECOVERY_BOUNDARY",
            "target_action": "HUMAN_DECISION_PACKAGE",
        }

    if candidate.reason in HOLD_REASONS:
        return {
            "status": "HOLD",
            "reason": "RECOVERY_EVIDENCE_OR_AUTHORITY_BLOCKER",
            "target_action": "NONE",
        }

    recipe = SAFE_PREPARE_RECIPES.get(candidate.reason)
    if recipe is None:
        return {
            "status": "HOLD",
            "reason": "UNREGISTERED_RECOVERY_REASON",
            "target_action": "NONE",
        }

    action, risk = recipe
    return {
        "status": "AUTO_PREPARE",
        "reason": candidate.reason,
        "target_action": action,
        "risk": risk,
    }


def build_recovery_plan(candidate: RecoveryCandidate) -> dict[str, Any]:
    pre = classify_candidate(candidate)
    if pre["status"] == "HOLD":
        return {
            "workload_id": candidate.project_id,
            "status": "HOLD",
            "reason": pre["reason"],
            "source_reason": candidate.reason,
            "target_action": pre["target_action"],
            "autonomous_ceiling": "PREPARE_PR",
            "production_authority": "HUMAN_ONLY",
            "external_action_execution": "DISABLED",
        }
    if pre["status"] == "HUMAN_REVIEW":
        return {
            "workload_id": candidate.project_id,
            "status": "HUMAN_REVIEW",
            "reason": pre["reason"],
            "source_reason": candidate.reason,
            "target_action": pre["target_action"],
            "steps": ["Prepare evidence-backed decision package; do not execute consequential recovery."],
            "autonomous_ceiling": "PREPARE_PR",
            "production_authority": "HUMAN_ONLY",
            "external_action_execution": "DISABLED",
        }

    planner = _load_planner()
    signal = planner.RemediationSignal(
        workload_id=candidate.project_id,
        action_class="AUTO_PREPARE",
        reason=candidate.reason,
        evidence_sha=candidate.evidence_sha,
        source_reference=candidate.source_reference,
        evidence_fresh=candidate.evidence_fresh,
        target_action=pre["target_action"],
        risk=pre["risk"],
        reversible=True,
        production=False,
    )
    plan = planner.build_plan(signal)
    plan["source_reason"] = candidate.reason
    plan["recipe_registered"] = True
    return plan


def plans_from_assessment(
    *,
    project_id: str,
    reasons: list[str],
    evidence_sha: str,
    source_reference: str,
    evidence_fresh: bool,
) -> list[dict[str, Any]]:
    if not reasons:
        return []
    plans = []
    for reason in sorted(set(reasons)):
        if reason in {"ALL_REQUIRED_SIGNALS_HEALTHY", "PROJECT_EVIDENCE_COMPLETE"}:
            continue
        plans.append(build_recovery_plan(RecoveryCandidate(
            project_id=project_id,
            reason=reason,
            evidence_sha=evidence_sha,
            source_reference=source_reference,
            evidence_fresh=evidence_fresh,
        )))
    priority = {"HOLD": 100, "HUMAN_REVIEW": 90, "PREPARE_PR": 70, "MONITOR": 20}
    plans.sort(key=lambda item: (-priority.get(item["status"], 1000), item.get("source_reason", "")))
    return plans
