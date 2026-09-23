from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_EVIDENCE = {"exact_main_sha", "fresh_ci", "source_reference"}
AUTHORITY = {
    "autonomous_ceiling": "PREPARE_PR",
    "production_authority": "HUMAN_ONLY",
    "protected_main_merge": "HUMAN_ONLY",
    "automatic_production_rollback": "DISABLED",
}


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_registry(registry: dict[str, Any], source_registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("version") != "1.0":
        return {"status": "HOLD", "reason": "JOURNEY_REGISTRY_VERSION_INVALID"}
    if registry.get("authority") != AUTHORITY:
        return {"status": "HOLD", "reason": "JOURNEY_AUTHORITY_BOUNDARY_INVALID"}

    sources = source_registry.get("sources")
    if source_registry.get("version") != "2.0" or not isinstance(sources, list):
        return {"status": "HOLD", "reason": "SOURCE_REGISTRY_V2_REQUIRED"}

    expected_projects = {item.get("project_id") for item in sources if item.get("project_id")}
    journeys = registry.get("journeys")
    if not isinstance(journeys, list) or not journeys:
        return {"status": "HOLD", "reason": "GOLDEN_JOURNEYS_REQUIRED"}

    seen_ids: set[tuple[str, str]] = set()
    covered: set[str] = set()
    errors: list[str] = []

    for item in journeys:
        if not isinstance(item, dict):
            errors.append("JOURNEY_NOT_OBJECT")
            continue
        project_id = item.get("project_id")
        journey_id = item.get("journey_id")
        key = (project_id, journey_id)
        if not project_id or not journey_id:
            errors.append("JOURNEY_IDENTITY_REQUIRED")
            continue
        if key in seen_ids:
            errors.append(f"DUPLICATE_JOURNEY:{project_id}:{journey_id}")
        seen_ids.add(key)
        covered.add(project_id)

        stages = item.get("stages")
        if not isinstance(stages, list) or len(stages) < 2 or any(not str(stage).strip() for stage in stages):
            errors.append(f"JOURNEY_STAGES_INVALID:{project_id}:{journey_id}")
        if item.get("critical") is not True:
            errors.append(f"P0_JOURNEY_MUST_BE_CRITICAL:{project_id}:{journey_id}")

        evidence = set(item.get("evidence_contract") or [])
        missing = REQUIRED_EVIDENCE - evidence
        if missing:
            errors.append(f"JOURNEY_EVIDENCE_INCOMPLETE:{project_id}:{journey_id}:{','.join(sorted(missing))}")

        forbidden = {"auto_production_deploy", "auto_merge", "auto_charge", "auto_legal_commitment"}
        if evidence & forbidden:
            errors.append(f"JOURNEY_FORBIDDEN_AUTHORITY:{project_id}:{journey_id}")

    missing_projects = sorted(expected_projects - covered)
    unknown_projects = sorted(covered - expected_projects)
    if missing_projects:
        errors.append("PROJECT_WITHOUT_GOLDEN_JOURNEY:" + ",".join(missing_projects))
    if unknown_projects:
        errors.append("UNKNOWN_GOLDEN_JOURNEY_PROJECT:" + ",".join(unknown_projects))

    if errors:
        return {"status": "HOLD", "reason": "JOURNEY_REGISTRY_INVALID", "errors": sorted(errors)}

    return {
        "status": "READY",
        "reason": "GOLDEN_JOURNEY_REGISTRY_VALID",
        "project_count": len(expected_projects),
        "journey_count": len(journeys),
        "covered_projects": sorted(covered),
        **AUTHORITY,
    }


def journey_index(registry: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in registry.get("journeys") or []:
        result.setdefault(item["project_id"], []).append(dict(item))
    for items in result.values():
        items.sort(key=lambda item: item["journey_id"])
    return result
