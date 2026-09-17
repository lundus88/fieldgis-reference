from __future__ import annotations

from typing import Iterable

from mission_control import ControlIntent, MissionInput, OperationalTelemetry, build_mission_control_view

TRUTH_SCHEMA = "lom.project-state-truth/1"
TRUTH_SOURCE = "LOM_6_10_PROJECT_STATE_TRUTH"
TRUSTED_PROJECT_STATES = {"VERIFIED", "APPROVED", "RELEASED"}
FAIL_CLOSED_PROJECT_STATES = {"UNVERIFIED", "HOLD", "FAILED"}
ALL_PROJECT_STATES = TRUSTED_PROJECT_STATES | FAIL_CLOSED_PROJECT_STATES


def _truth_hold(reason: str) -> dict:
    return {
        "status": "HOLD",
        "reason": reason,
        "source": TRUTH_SOURCE,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "execution_authority": "NONE",
        "execution_performed": False,
    }


def validate_project_truth_snapshot(snapshot: dict | None) -> dict:
    """Validate the canonical LOM 6.10 snapshot contract fail-closed."""
    if snapshot is None:
        return _truth_hold("PROJECT_TRUTH_REQUIRED")
    if not isinstance(snapshot, dict):
        return _truth_hold("PROJECT_TRUTH_INVALID_TYPE")
    if snapshot.get("schema") != TRUTH_SCHEMA:
        return _truth_hold("PROJECT_TRUTH_SCHEMA_INVALID")
    if snapshot.get("autonomous_ceiling") != "PREPARE_PR":
        return _truth_hold("PROJECT_TRUTH_AUTHORITY_MISMATCH")
    if snapshot.get("production_authority") != "HUMAN_ONLY":
        return _truth_hold("PROJECT_TRUTH_AUTHORITY_MISMATCH")
    if snapshot.get("protected_main_merge") != "HUMAN_ONLY":
        return _truth_hold("PROJECT_TRUTH_AUTHORITY_MISMATCH")
    if snapshot.get("execution_authority") != "NONE":
        return _truth_hold("PROJECT_TRUTH_EXECUTION_AUTHORITY_INVALID")
    if snapshot.get("execution_performed") is not False:
        return _truth_hold("PROJECT_TRUTH_EXECUTION_STATE_INVALID")

    fingerprint = snapshot.get("snapshot_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        return _truth_hold("PROJECT_TRUTH_FINGERPRINT_REQUIRED")

    projects = snapshot.get("projects")
    if not isinstance(projects, list):
        return _truth_hold("PROJECT_TRUTH_PROJECTS_REQUIRED")

    index: dict[str, dict] = {}
    for item in projects:
        if not isinstance(item, dict):
            return _truth_hold("PROJECT_TRUTH_PROJECT_INVALID")
        project_id = item.get("project_id")
        status = item.get("status")
        reason = item.get("reason")
        if not isinstance(project_id, str) or not project_id:
            return _truth_hold("PROJECT_TRUTH_PROJECT_ID_REQUIRED")
        if project_id in index:
            return _truth_hold("PROJECT_TRUTH_DUPLICATE_PROJECT")
        if status not in ALL_PROJECT_STATES:
            return _truth_hold("PROJECT_TRUTH_STATE_INVALID")
        if not isinstance(reason, str) or not reason:
            return _truth_hold("PROJECT_TRUTH_REASON_REQUIRED")
        index[project_id] = {
            "project_id": project_id,
            "status": status,
            "reason": reason,
        }

    return {
        "status": "VALID",
        "reason": "PROJECT_TRUTH_VALID",
        "source": TRUTH_SOURCE,
        "schema": TRUTH_SCHEMA,
        "snapshot_fingerprint": fingerprint,
        "truth_overall": snapshot.get("overall"),
        "projects": index,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "execution_authority": "NONE",
        "execution_performed": False,
    }


def _bind_telemetry_to_truth(cards: list[dict], truth: dict) -> tuple[list[dict], int, int]:
    bound: list[dict] = []
    missing = 0
    blocked = 0
    project_index = truth["projects"]
    fingerprint = truth["snapshot_fingerprint"]

    for card in cards:
        item = dict(card)
        project_id = item.get("project_id")
        project_truth = project_index.get(project_id)
        if project_truth is None:
            missing += 1
            item.update(
                {
                    "project_status_source": TRUTH_SOURCE,
                    "canonical_project_state": "HOLD",
                    "canonical_project_reason": "PROJECT_TRUTH_MISSING_FOR_PROJECT",
                    "project_truth_fingerprint": fingerprint,
                    "effective_action_class": "HOLD",
                }
            )
        else:
            canonical_state = project_truth["status"]
            if canonical_state in FAIL_CLOSED_PROJECT_STATES:
                blocked += 1
                effective = "HOLD"
            else:
                effective = item["action_class"]
            item.update(
                {
                    "project_status_source": TRUTH_SOURCE,
                    "canonical_project_state": canonical_state,
                    "canonical_project_reason": project_truth["reason"],
                    "project_truth_fingerprint": fingerprint,
                    "effective_action_class": effective,
                }
            )
        bound.append(item)

    return bound, missing, blocked


def build_truth_bound_mission_control_view(
    missions: Iterable[MissionInput],
    telemetry: Iterable[OperationalTelemetry] = (),
    control_intents: Iterable[ControlIntent] = (),
    project_truth_snapshot: dict | None = None,
) -> dict:
    """Compose Director Mission Control using LOM 6.10 as project status authority.

    The original Mission Control v2 builder remains unchanged for backward
    compatibility. This governed entrypoint is the canonical path for callers
    that require evidence-bound project status. It never executes controls.
    """
    base = build_mission_control_view(missions, telemetry, control_intents)
    truth = validate_project_truth_snapshot(project_truth_snapshot)

    result = dict(base)
    result["schema_version"] = 3
    result["project_status_authority"] = TRUTH_SOURCE

    if truth["status"] != "VALID":
        result["overall_action_class"] = "HOLD"
        result["project_truth"] = truth
        result["portfolio"] = {
            **base["portfolio"],
            "truth_bound_project_count": 0,
            "truth_missing_project_count": len(base["telemetry"]),
            "truth_blocked_project_count": 0,
        }
        result["autonomous_ceiling"] = "PREPARE_PR"
        result["control_execution"] = "DISABLED"
        result["production_authority"] = "HUMAN_ONLY"
        result["protected_main_merge"] = "HUMAN_ONLY"
        return result

    bound_cards, missing, blocked = _bind_telemetry_to_truth(base["telemetry"], truth)
    result["telemetry"] = bound_cards
    result["project_truth"] = {
        "status": "BOUND",
        "reason": "CANONICAL_PROJECT_TRUTH_BOUND",
        "source": TRUTH_SOURCE,
        "schema": truth["schema"],
        "snapshot_fingerprint": truth["snapshot_fingerprint"],
        "truth_overall": truth["truth_overall"],
        "project_count": len(truth["projects"]),
        "projects": [truth["projects"][key] for key in sorted(truth["projects"])],
        "execution_authority": "NONE",
        "execution_performed": False,
        "production_authority": "HUMAN_ONLY",
    }
    result["portfolio"] = {
        **base["portfolio"],
        "truth_bound_project_count": len(bound_cards) - missing,
        "truth_missing_project_count": missing,
        "truth_blocked_project_count": blocked,
    }

    if missing > 0 or blocked > 0:
        result["overall_action_class"] = "HOLD"
    elif truth["truth_overall"] in {"HOLD", "FAILED"}:
        result["overall_action_class"] = "HOLD"
    elif any(card["effective_action_class"] == "HOLD" for card in bound_cards):
        result["overall_action_class"] = "HOLD"
    elif any(card["effective_action_class"] == "HUMAN_REVIEW" for card in bound_cards):
        result["overall_action_class"] = "HUMAN_REVIEW"

    result["autonomous_ceiling"] = "PREPARE_PR"
    result["control_execution"] = "DISABLED"
    result["production_authority"] = "HUMAN_ONLY"
    result["protected_main_merge"] = "HUMAN_ONLY"
    return result
