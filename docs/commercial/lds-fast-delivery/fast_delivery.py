#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, Any

PROJECT_CLASSES = {
    "QUICK_AUTOMATION": (3, 7, 1, 3),
    "STARTER_SYSTEM": (5, 15, 3, 8),
    "SEMI_CUSTOM": (15, 30, 8, 20),
    "COMPLEX": (None, None, 20, None),
}

@dataclass(frozen=True)
class Intake:
    qualified: bool
    scope_bounded: bool
    dependencies_ready: bool
    effort_points: int
    lane: str = "STANDARD"
    urgent: bool = False

def classify_project(effort_points: int) -> str:
    if effort_points < 1:
        raise ValueError("effort_points must be >= 1")
    if effort_points <= 3:
        return "QUICK_AUTOMATION"
    if effort_points <= 8:
        return "STARTER_SYSTEM"
    if effort_points <= 20:
        return "SEMI_CUSTOM"
    return "COMPLEX"

def plan_intake(intake: Intake, active_points: int, capacity_points: int) -> Dict[str, Any]:
    if capacity_points < 1 or active_points < 0:
        raise ValueError("invalid capacity")
    if intake.lane not in {"STANDARD", "FAST_TRACK"}:
        raise ValueError("invalid lane")
    project_class = classify_project(intake.effort_points)

    if not intake.qualified:
        return {"state":"HOLD","reason":"NOT_QUALIFIED","project_class":project_class}
    if not intake.scope_bounded:
        return {"state":"CLIENT_ACTION_REQUIRED","reason":"SCOPE_UNBOUNDED","project_class":project_class}
    if not intake.dependencies_ready:
        return {"state":"CLIENT_ACTION_REQUIRED","reason":"DEPENDENCIES_NOT_READY","project_class":project_class}

    available = max(capacity_points - active_points, 0)
    capacity_ok = intake.effort_points <= available

    if intake.lane == "FAST_TRACK" and not capacity_ok:
        return {"state":"SCHEDULED","reason":"FAST_TRACK_CAPACITY_NOT_RESERVED","project_class":project_class}

    if not capacity_ok:
        return {"state":"SCHEDULED","reason":"CAPACITY_EXHAUSTED","project_class":project_class}

    band = PROJECT_CLASSES[project_class]
    target = "MILESTONE_BASED" if project_class == "COMPLEX" else {
        "min_business_days": band[0],
        "max_business_days": band[1],
    }
    return {
        "state":"BUILDING",
        "reason":"BUILD_ENTRY_READY",
        "project_class":project_class,
        "lane":intake.lane,
        "target":target,
        "first_visible_value_hours":{"min":48,"max":72},
        "final_acceptance_authority":"HUMAN_ONLY",
    }

def uat_transition(client_acceptance: str, unresolved_severity: str = "NONE") -> Dict[str, str]:
    allowed = {"PENDING","ACCEPTED","ACCEPTED_WITH_MINOR_ISSUES","REJECTED"}
    if client_acceptance not in allowed:
        raise ValueError("invalid client acceptance")
    if client_acceptance == "PENDING":
        return {"state":"UAT","action":"WAIT_FOR_HUMAN_ACCEPTANCE"}
    if client_acceptance == "REJECTED":
        return {"state":"BUILDING","action":"VL_REMEDIATE_AND_RETEST"}
    if unresolved_severity in {"CRITICAL","HIGH"}:
        return {"state":"BLOCKED","action":"REMEDIATE_BEFORE_DELIVERY"}
    return {"state":"DELIVERY","action":"PREPARE_HUMAN_APPROVED_HANDOVER"}
