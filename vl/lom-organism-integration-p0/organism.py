from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]

ORGANS = {
    "brain",
    "eyes",
    "ears",
    "nervous_system",
    "memory",
    "immune_system",
    "heart",
    "hands",
    "voice",
}

ALLOWED_SIGNAL_TYPES = {
    "HEALTH",
    "DRIFT",
    "REGRESSION",
    "SECURITY",
    "OPPORTUNITY",
    "WORK_READY",
    "AUTHORITY_REQUEST",
    "EVIDENCE_GAP",
    "INCIDENT",
}

ALLOWED_SEVERITY = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
SEVERITY_SCORE = {"INFO": 0, "LOW": 10, "MEDIUM": 30, "HIGH": 70, "CRITICAL": 100}
HUMAN_ONLY_ACTIONS = {
    "MERGE_PROTECTED_MAIN",
    "PRODUCTION_DEPLOY",
    "PRODUCTION_DATA_MUTATION",
    "PRODUCTION_AUTHORITY_CHANGE",
    "FINANCIAL_OR_CONTRACTUAL_COMMITMENT",
    "CUSTOMER_COMMITMENT",
    "BID_SUBMISSION",
    "PRICING_COMMITMENT",
    "LEGAL_COMMITMENT",
}

ROUTE = {
    "HEALTH": ("eyes", "nervous_system", "heart"),
    "DRIFT": ("eyes", "memory", "nervous_system"),
    "REGRESSION": ("eyes", "brain", "nervous_system", "hands"),
    "SECURITY": ("immune_system", "memory", "nervous_system"),
    "OPPORTUNITY": ("ears", "brain", "nervous_system"),
    "WORK_READY": ("brain", "nervous_system", "hands"),
    "AUTHORITY_REQUEST": ("nervous_system", "voice"),
    "EVIDENCE_GAP": ("eyes", "memory", "heart"),
    "INCIDENT": ("immune_system", "heart", "nervous_system", "voice"),
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


@dataclass(frozen=True)
class SensorySignal:
    signal_id: str
    source_organ: str
    project_id: str
    signal_type: str
    severity: str
    observed_at_epoch: int
    expires_at_epoch: int
    evidence_refs: tuple[str, ...]
    requested_action: str | None = None
    production: bool = False
    reversible: bool = True
    risk: str = "LOW"


def load_registry(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_body_registry(registry: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    if registry.get("version") != "1.0" or registry.get("mode") != "NON_PRODUCTION_INTEGRATION":
        return {"status": "HOLD", "reason": "BODY_REGISTRY_VERSION_INVALID"}

    required = set(registry.get("required_organs") or [])
    if required != ORGANS:
        return {
            "status": "HOLD",
            "reason": "REQUIRED_ORGAN_SET_INVALID",
            "missing": sorted(ORGANS - required),
            "unknown": sorted(required - ORGANS),
        }

    organs = registry.get("organs")
    if not isinstance(organs, list) or len(organs) != len(ORGANS):
        return {"status": "HOLD", "reason": "ORGAN_REGISTRY_INCOMPLETE"}

    seen: set[str] = set()
    missing_components: list[str] = []
    for organ in organs:
        name = organ.get("organ")
        if name not in ORGANS or name in seen:
            return {"status": "HOLD", "reason": "ORGAN_ID_INVALID_OR_DUPLICATE"}
        seen.add(name)
        components = organ.get("canonical_components")
        if not isinstance(components, list) or not components:
            return {"status": "HOLD", "reason": "ORGAN_COMPONENTS_REQUIRED", "organ": name}
        for component in components:
            if not (root / component).exists():
                missing_components.append(component)

    if missing_components:
        return {
            "status": "HOLD",
            "reason": "CANONICAL_COMPONENT_MISSING",
            "components": sorted(missing_components),
        }

    authority = registry.get("authority") or {}
    if authority.get("autonomous_ceiling") != "PREPARE_PR":
        return {"status": "HOLD", "reason": "AUTONOMOUS_CEILING_WEAKENED"}
    required_human = {
        "protected_main_merge",
        "production_deploy",
        "production_data_mutation",
        "production_authority_change",
        "financial_contractual_customer_commitment",
    }
    for key in required_human:
        if authority.get(key) != "HUMAN_ONLY":
            return {"status": "HOLD", "reason": "HUMAN_AUTHORITY_WEAKENED", "authority": key}

    loop = registry.get("closed_loop")
    expected = [
        "SENSE",
        "ESTABLISH_TRUTH",
        "CLASSIFY",
        "POLICY_GATE",
        "DECIDE",
        "PREPARE_OR_EXECUTE_BOUNDED",
        "VALIDATE",
        "RECORD_EVIDENCE",
        "LEARN",
    ]
    if loop != expected:
        return {"status": "HOLD", "reason": "CLOSED_LOOP_ORDER_INVALID"}

    return {
        "status": "READY",
        "reason": "BODY_REGISTRY_VALID",
        "organs": sorted(seen),
        "component_count": sum(len(o["canonical_components"]) for o in organs),
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
    }


def validate_signal(signal: SensorySignal, *, now_epoch: int) -> dict[str, Any]:
    if not signal.signal_id or not signal.project_id:
        return {"status": "HOLD", "reason": "SIGNAL_IDENTITY_REQUIRED"}
    if signal.source_organ not in ORGANS:
        return {"status": "HOLD", "reason": "UNKNOWN_SOURCE_ORGAN"}
    if signal.signal_type not in ALLOWED_SIGNAL_TYPES:
        return {"status": "HOLD", "reason": "UNKNOWN_SIGNAL_TYPE"}
    if signal.severity not in ALLOWED_SEVERITY:
        return {"status": "HOLD", "reason": "UNKNOWN_SIGNAL_SEVERITY"}
    if not signal.evidence_refs:
        return {"status": "HOLD", "reason": "SIGNAL_EVIDENCE_REQUIRED"}
    if signal.observed_at_epoch <= 0 or signal.observed_at_epoch > now_epoch:
        return {"status": "HOLD", "reason": "SIGNAL_TIME_INVALID"}
    if signal.expires_at_epoch < now_epoch or signal.expires_at_epoch < signal.observed_at_epoch:
        return {"status": "HOLD", "reason": "SIGNAL_STALE"}
    if signal.risk not in {"LOW", "MEDIUM", "HIGH"}:
        return {"status": "HOLD", "reason": "UNKNOWN_RISK"}
    return {"status": "READY", "reason": "SIGNAL_VALID"}


def route_signal(signal: SensorySignal, *, now_epoch: int) -> dict[str, Any]:
    valid = validate_signal(signal, now_epoch=now_epoch)
    if valid["status"] != "READY":
        return _decision(signal, "HOLD", valid["reason"], ("eyes", "memory"))

    route = ROUTE[signal.signal_type]
    action = signal.requested_action

    if action in HUMAN_ONLY_ACTIONS or signal.production:
        return _decision(
            signal,
            "HUMAN_REVIEW",
            "CONSEQUENTIAL_BOUNDARY",
            tuple(dict.fromkeys(route + ("voice",))),
        )

    if signal.signal_type == "SECURITY":
        return _decision(signal, "HOLD", "SECURITY_SIGNAL_REQUIRES_CONTAINMENT_REVIEW", route)

    if signal.signal_type == "INCIDENT" and signal.severity in {"HIGH", "CRITICAL"}:
        return _decision(signal, "HUMAN_REVIEW", "HIGH_SEVERITY_INCIDENT", route)

    if signal.severity == "CRITICAL":
        return _decision(signal, "HUMAN_REVIEW", "CRITICAL_SIGNAL", route)

    if signal.signal_type == "EVIDENCE_GAP":
        return _decision(signal, "HOLD", "TRUTH_MUST_BE_RESTORED_BEFORE_ACTION", route)

    if signal.signal_type == "AUTHORITY_REQUEST":
        return _decision(signal, "HUMAN_REVIEW", "EXPLICIT_AUTHORITY_REQUIRED", route)

    if signal.signal_type in {"REGRESSION", "DRIFT"}:
        if signal.risk == "LOW" and signal.reversible:
            return _decision(signal, "AUTO_PREPARE", "BOUNDED_REMEDIATION_CANDIDATE", route)
        return _decision(signal, "HUMAN_REVIEW", "REMEDIATION_NOT_LOW_RISK_REVERSIBLE", route)

    if signal.signal_type == "WORK_READY":
        if signal.risk == "LOW" and signal.reversible:
            return _decision(signal, "AUTO_PREPARE", "READY_FOR_BOUNDED_NONPROD_PREPARATION", route)
        return _decision(signal, "HUMAN_REVIEW", "WORK_REQUIRES_REVIEW", route)

    if signal.signal_type == "OPPORTUNITY":
        return _decision(signal, "MONITOR", "OPPORTUNITY_REQUIRES_QUALIFICATION", route)

    return _decision(signal, "MONITOR", "READ_ONLY_OBSERVATION", route)


def _decision(signal: SensorySignal, action_class: str, reason: str, route: tuple[str, ...]) -> dict[str, Any]:
    body = {
        "schema": "lom.organism-route/1",
        "signal_id": signal.signal_id,
        "project_id": signal.project_id,
        "signal_type": signal.signal_type,
        "severity": signal.severity,
        "action_class": action_class,
        "reason": reason,
        "route": list(route),
        "evidence_refs": sorted(set(signal.evidence_refs)),
        "observed_at_epoch": signal.observed_at_epoch,
        "expires_at_epoch": signal.expires_at_epoch,
        "requested_action": signal.requested_action,
        "production": signal.production,
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }
    return {**body, "route_digest": digest(body)}


def homeostasis(
    registry: dict[str, Any],
    organ_states: Iterable[dict[str, Any]],
    *,
    now_epoch: int,
    max_age_seconds: int,
) -> dict[str, Any]:
    body_check = validate_body_registry(registry)
    if body_check["status"] != "READY":
        return {
            "schema": "lom.organism-homeostasis/1",
            "status": "HOLD",
            "reason": body_check["reason"],
            "autonomous_ceiling": "PREPARE_PR",
            "execution_authority": "NONE",
        }

    rows = list(organ_states)
    by_organ: dict[str, dict[str, Any]] = {}
    violations: list[str] = []
    for row in rows:
        organ = row.get("organ")
        if organ not in ORGANS or organ in by_organ:
            violations.append("UNKNOWN_OR_DUPLICATE_ORGAN_STATE")
            continue
        observed = row.get("observed_at_epoch")
        evidence = row.get("evidence_refs")
        status = row.get("status")
        if status not in {"HEALTHY", "DEGRADED", "HOLD", "FAILED"}:
            violations.append(f"INVALID_ORGAN_STATUS:{organ}")
            continue
        if not isinstance(observed, int) or observed <= 0 or observed > now_epoch:
            violations.append(f"INVALID_ORGAN_TIME:{organ}")
            continue
        if now_epoch - observed > max_age_seconds:
            status = "HOLD"
            row = {**row, "status": status, "reason": "ORGAN_EVIDENCE_STALE"}
        if not evidence:
            status = "HOLD"
            row = {**row, "status": status, "reason": "ORGAN_EVIDENCE_REQUIRED"}
        by_organ[organ] = row

    missing = sorted(ORGANS - set(by_organ))
    if missing:
        violations.append("MISSING_ORGAN_STATE:" + ",".join(missing))

    rank = {"HEALTHY": 0, "DEGRADED": 1, "HOLD": 2, "FAILED": 3}
    overall = "HEALTHY"
    for row in by_organ.values():
        if rank[row["status"]] > rank[overall]:
            overall = row["status"]
    if violations and rank["HOLD"] > rank[overall]:
        overall = "HOLD"

    reason = "ALL_ORGANS_WITHIN_BOUNDARY"
    if overall == "DEGRADED":
        reason = "ORGAN_DEGRADATION_PRESENT"
    elif overall == "HOLD":
        reason = "ORGAN_OR_EVIDENCE_HOLD"
    elif overall == "FAILED":
        reason = "ORGAN_FAILURE_PRESENT"

    result = {
        "schema": "lom.organism-homeostasis/1",
        "status": overall,
        "reason": reason,
        "organs": [by_organ[name] for name in sorted(by_organ)],
        "missing_organs": missing,
        "violations": sorted(violations),
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }
    return {**result, "homeostasis_digest": digest(result)}


def build_reflex_plan(route: dict[str, Any]) -> dict[str, Any]:
    action_class = route.get("action_class")
    if route.get("schema") != "lom.organism-route/1":
        return {"status": "HOLD", "reason": "ROUTE_SCHEMA_INVALID", "steps": []}

    steps = [
        "VERIFY_EVIDENCE",
        "ESTABLISH_TRUTH",
        "CHECK_AUTHORITY",
    ]

    if action_class == "AUTO_PREPARE":
        steps += ["PREPARE_BOUNDED_CANDIDATE", "INDEPENDENT_VALIDATE", "RECORD_EVIDENCE"]
        status = "PREPARE_PR"
    elif action_class == "HUMAN_REVIEW":
        steps += ["PREPARE_HUMAN_DECISION_PACKAGE", "STOP"]
        status = "HUMAN_REVIEW"
    elif action_class == "MONITOR":
        steps += ["REFRESH_EVIDENCE"]
        status = "MONITOR"
    else:
        steps += ["STOP_AND_RESTORE_TRUTH"]
        status = "HOLD"

    return {
        "schema": "lom.organism-reflex-plan/1",
        "signal_id": route.get("signal_id"),
        "status": status,
        "steps": steps,
        "external_execution": "DISABLED",
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }
