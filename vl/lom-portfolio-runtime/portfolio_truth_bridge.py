from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
READ_ONLY = "READ_ONLY"
UNREGISTERED_HOLD = "UNREGISTERED_HOLD"
FAIL_CLOSED_STATES = {"UNVERIFIED", "HOLD", "FAILED"}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_truth_runtime():
    truth = _load_module(
        "portfolio_project_state_truth",
        ROOT / "lom-6-10-project-state-truth-layer" / "project_state_truth.py",
    )
    ledger = _load_module(
        "portfolio_event_ledger",
        ROOT / "lom-operational-safety" / "event_ledger.py",
    )
    return truth, ledger


def _load_mission_control_runtime():
    mission = _load_module(
        "mission_control",
        ROOT / "lom-mission-control" / "mission_control.py",
    )
    bound = _load_module(
        "portfolio_truth_bound_mission_control",
        ROOT / "lom-mission-control" / "truth_bound_mission_control.py",
    )
    return mission, bound


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def _epoch(value: str | None, fallback: int) -> int:
    if not value:
        return fallback
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def validate_source_registry(registry: dict) -> list[dict]:
    if not isinstance(registry, dict):
        raise ValueError("SOURCE_REGISTRY_REQUIRED")
    if registry.get("version") != "2.0":
        raise ValueError("SOURCE_REGISTRY_V2_REQUIRED")
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("SOURCE_REGISTRY_SOURCES_REQUIRED")

    project_ids: set[str] = set()
    objective_ids: set[str] = set()
    normalized: list[dict] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("SOURCE_DECLARATION_INVALID")
        project_id = source.get("project_id")
        objective_id = source.get("objective_id")
        name = source.get("name")
        mode = source.get("mode")
        if not project_id or not objective_id or not name:
            raise ValueError("SOURCE_IDENTITY_REQUIRED")
        if project_id in project_ids:
            raise ValueError("DUPLICATE_PROJECT_ID")
        if objective_id in objective_ids:
            raise ValueError("DUPLICATE_OBJECTIVE_ID")
        project_ids.add(project_id)
        objective_ids.add(objective_id)

        if mode == READ_ONLY:
            if not source.get("repository") or not source.get("default_branch"):
                raise ValueError("READ_ONLY_SOURCE_REPOSITORY_REQUIRED")
        elif mode == UNREGISTERED_HOLD:
            if source.get("repository") or source.get("default_branch"):
                raise ValueError("UNREGISTERED_SOURCE_MUST_NOT_INVENT_REPOSITORY")
            if not source.get("hold_reason"):
                raise ValueError("UNREGISTERED_SOURCE_HOLD_REASON_REQUIRED")
        else:
            raise ValueError("UNKNOWN_SOURCE_MODE")
        normalized.append(dict(source))
    return normalized


def _observation_index(payload: dict) -> tuple[dict[str, dict], int]:
    if not isinstance(payload, dict):
        raise ValueError("PORTFOLIO_OBSERVATION_REQUIRED")
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise ValueError("PORTFOLIO_OBSERVATIONS_REQUIRED")
    captured_epoch = _epoch(payload.get("captured_at"), 0)
    index: dict[str, dict] = {}
    for item in observations:
        if not isinstance(item, dict) or not item.get("project_id"):
            raise ValueError("PORTFOLIO_OBSERVATION_PROJECT_ID_REQUIRED")
        project_id = item["project_id"]
        if project_id in index:
            raise ValueError("DUPLICATE_PORTFOLIO_OBSERVATION")
        index[project_id] = item
    return index, captured_epoch


def _derive_source_state(source: dict, observed: dict | None) -> tuple[str, str]:
    if source["mode"] == UNREGISTERED_HOLD:
        return "HOLD", source["hold_reason"]
    if observed is None:
        return "HOLD", "SOURCE_OBSERVATION_MISSING"
    if observed.get("repository") != source.get("repository"):
        return "HOLD", "SOURCE_REPOSITORY_MISMATCH"
    signals = {str(value) for value in (observed.get("signals") or [])}
    if not observed.get("accessible"):
        return "HOLD", "SOURCE_NOT_ACCESSIBLE"
    if not observed.get("main_sha"):
        return "HOLD", "SOURCE_MAIN_SHA_MISSING"
    if "EMPTY_REPOSITORY" in signals:
        return "HOLD", "EMPTY_REPOSITORY"
    if "SOURCE_NOT_REFRESHED" in signals:
        return "HOLD", "SOURCE_NOT_REFRESHED"
    if any("BLOCKED" in signal for signal in signals):
        return "HOLD", "SOURCE_BLOCKED_SIGNAL"
    return "UNVERIFIED", "REPOSITORY_EVIDENCE_ONLY"


def build_project_truth_snapshot(
    registry: dict,
    observation_payload: dict,
    now_epoch: int,
    max_observation_age_seconds: int = 86400,
) -> dict:
    """Bind portfolio sources into canonical LOM 6.10 Project State Truth.

    Repository evidence alone is never promoted to VERIFIED. It can establish
    UNVERIFIED presence or a fail-closed HOLD condition only.
    """
    if max_observation_age_seconds <= 0:
        raise ValueError("POSITIVE_OBSERVATION_MAX_AGE_REQUIRED")
    sources = validate_source_registry(registry)
    observed_by_project, captured_epoch = _observation_index(observation_payload)
    truth, ledger_module = _load_truth_runtime()

    evidence_registry = truth.EvidenceRegistry()
    ledger = ledger_module.AppendOnlyEventLedger()
    project_observations = []
    bindings = []

    for source in sources:
        project_id = source["project_id"]
        objective_id = source["objective_id"]
        observed = observed_by_project.get(project_id)
        state, binding_reason = _derive_source_state(source, observed)

        if source["mode"] == UNREGISTERED_HOLD or observed is None:
            observed_epoch = now_epoch
            evidence_refs = [
                "registry:vl/lom-portfolio-runtime/source-registry.json",
                f"status:{binding_reason}",
            ]
        else:
            observed_epoch = int(observed.get("observed_at_epoch") or captured_epoch or now_epoch)
            evidence_refs = list(observed.get("evidence_refs") or [])
            if not evidence_refs:
                evidence_refs = [f"repository:{source['repository']}", f"status:{binding_reason}"]

        ledger_state = "HOLD" if state == "HOLD" else "VALIDATING"
        event = ledger.append(
            "portfolio-truth-binding",
            objective_id,
            "lom-portfolio-truth-bridge",
            "BIND_PORTFOLIO_SOURCE",
            evidence_refs,
            "PLANNED",
            ledger_state,
            binding_reason,
            observed_epoch,
        )
        evidence_id = f"portfolio:{project_id}:{event['sequence']}"
        evidence_registry.register(
            truth.EvidenceRecord(
                evidence_id=evidence_id,
                project_id=project_id,
                objective_id=objective_id,
                evidence_type="PORTFOLIO_SOURCE_OBSERVATION",
                result="PASS",
                source_reference="|".join(evidence_refs),
                observed_at_epoch=observed_epoch,
                expires_at_epoch=observed_epoch + max_observation_age_seconds,
                actor_id="lom-portfolio-truth-bridge",
                independent=False,
                human_approval=False,
                contradictory=False,
                ledger_event_hash=event["event_hash"],
            )
        )
        project_observations.append(
            truth.ProjectObservation(
                project_id=project_id,
                objective_id=objective_id,
                state=state,
                evidence_ids=(evidence_id,),
                observed_at_epoch=observed_epoch,
            )
        )
        bindings.append(
            {
                "project_id": project_id,
                "name": source["name"],
                "objective_id": objective_id,
                "source_mode": source["mode"],
                "repository": source.get("repository"),
                "binding_state": state,
                "binding_reason": binding_reason,
            }
        )

    graph = truth.ProjectStateTruthGraph(evidence_registry, ledger)
    snapshot = graph.build_snapshot(project_observations, now_epoch)
    binding_fingerprint = _digest(bindings)
    snapshot["portfolio_binding"] = {
        "schema": "lom.portfolio-truth-binding/1",
        "source_registry_version": registry["version"],
        "registered_project_count": len(bindings),
        "projects": bindings,
        "binding_fingerprint": binding_fingerprint,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "execution_authority": "NONE",
        "execution_performed": False,
    }
    return snapshot


def build_portfolio_director_view(
    registry: dict,
    observation_payload: dict,
    now_epoch: int,
    missions: Iterable = (),
    telemetry: Iterable = (),
    control_intents: Iterable = (),
    max_observation_age_seconds: int = 86400,
) -> dict:
    snapshot = build_project_truth_snapshot(
        registry,
        observation_payload,
        now_epoch,
        max_observation_age_seconds=max_observation_age_seconds,
    )
    _, bound = _load_mission_control_runtime()
    view = bound.build_truth_bound_mission_control_view(
        missions,
        telemetry,
        control_intents,
        project_truth_snapshot=snapshot,
    )
    unready = sum(item["status"] in FAIL_CLOSED_STATES for item in snapshot["projects"])
    if unready:
        view["overall_action_class"] = "HOLD"
    view["portfolio_catalog"] = snapshot["portfolio_binding"]
    view["portfolio"] = {
        **view["portfolio"],
        "registered_project_count": snapshot["portfolio_binding"]["registered_project_count"],
        "truth_unready_catalog_count": unready,
    }
    view["autonomous_ceiling"] = "PREPARE_PR"
    view["control_execution"] = "DISABLED"
    view["production_authority"] = "HUMAN_ONLY"
    view["protected_main_merge"] = "HUMAN_ONLY"
    return view
