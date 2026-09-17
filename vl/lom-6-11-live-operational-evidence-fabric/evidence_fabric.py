from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "lom.operational-evidence/1"
FABRIC_SCHEMA = "lom.live-operational-evidence-fabric/1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
READ_ONLY = "READ_ONLY"
UNREGISTERED_HOLD = "UNREGISTERED_HOLD"
ALLOWED_SIGNAL_TYPES = {
    "CI_RUN",
    "RUNTIME_HEALTH",
    "AUTH_PATH",
    "DEPLOYMENT_STATE",
    "BACKGROUND_JOB",
}
REQUIRED_SIGNAL_TYPES = {"CI_RUN", "RUNTIME_HEALTH"}
RECOMMENDED_SIGNAL_TYPES = {"AUTH_PATH", "DEPLOYMENT_STATE", "BACKGROUND_JOB"}
ALLOWED_RESULTS = {"PASS", "FAIL", "HOLD"}
ALLOWED_DEPLOYMENT_STATES = {
    "READY",
    "PREVIEW",
    "DEGRADED",
    "FAILED",
    "UNKNOWN",
    "NOT_APPLICABLE",
}
ALLOWED_JOB_STATES = {"SUCCESS", "FAILED", "RUNNING", "UNKNOWN", "NOT_APPLICABLE"}


@dataclass(frozen=True)
class TechnicalMetrics:
    sample_count: int
    success_rate: float
    correctness: float
    safety: float
    p95_latency_ms: int
    source_kind: str = "nonprod_runtime"


@dataclass(frozen=True)
class OperationalEvidence:
    project_id: str
    objective_id: str
    repository: str
    evidence_sha: str
    signal_type: str
    result: str
    observed_at_epoch: int
    source_reference: str
    independent: bool = False
    production_sensitive: bool = False
    latency_ms: int | None = None
    error_rate: float | None = None
    deployment_state: str | None = None
    job_status: str | None = None
    technical_metrics: TechnicalMetrics | None = None
    schema: str = SCHEMA


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_LOAD_FAILED:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_telemetry_collector():
    return _load_module(
        "lom611_telemetry_collector",
        ROOT / "lom-6-3-telemetry-collection-pilot" / "collector.py",
    )


def _source_index(registry: dict) -> dict[str, dict]:
    if not isinstance(registry, dict) or registry.get("version") != "2.0":
        raise ValueError("SOURCE_REGISTRY_V2_REQUIRED")
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("SOURCE_REGISTRY_SOURCES_REQUIRED")
    index: dict[str, dict] = {}
    for source in sources:
        if not isinstance(source, dict) or not source.get("project_id") or not source.get("objective_id"):
            raise ValueError("SOURCE_IDENTITY_REQUIRED")
        if source["project_id"] in index:
            raise ValueError("DUPLICATE_PROJECT_ID")
        mode = source.get("mode")
        if mode == READ_ONLY:
            if not source.get("repository") or not source.get("default_branch"):
                raise ValueError("READ_ONLY_SOURCE_REPOSITORY_REQUIRED")
        elif mode == UNREGISTERED_HOLD:
            if source.get("repository") or not source.get("hold_reason"):
                raise ValueError("UNREGISTERED_SOURCE_DECLARATION_INVALID")
        else:
            raise ValueError("UNKNOWN_SOURCE_MODE")
        index[source["project_id"]] = dict(source)
    return index


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def validate_evidence(
    evidence: OperationalEvidence,
    source: dict,
    *,
    now_epoch: int,
    max_age_seconds: int = 172800,
) -> dict:
    if max_age_seconds <= 0:
        raise ValueError("POSITIVE_MAX_AGE_REQUIRED")
    if evidence.schema != SCHEMA:
        return {"status": "HOLD", "reason": "SCHEMA_MISMATCH"}
    if source.get("mode") != READ_ONLY:
        return {"status": "HOLD", "reason": "SOURCE_NOT_READ_ONLY"}
    if evidence.project_id != source.get("project_id") or evidence.objective_id != source.get("objective_id"):
        return {"status": "HOLD", "reason": "EVIDENCE_SCOPE_MISMATCH"}
    if evidence.repository != source.get("repository"):
        return {"status": "HOLD", "reason": "SOURCE_REPOSITORY_MISMATCH"}
    if not SHA_RE.fullmatch(evidence.evidence_sha or ""):
        return {"status": "HOLD", "reason": "INVALID_EVIDENCE_SHA"}
    if evidence.signal_type not in ALLOWED_SIGNAL_TYPES:
        return {"status": "HOLD", "reason": "UNKNOWN_SIGNAL_TYPE"}
    if evidence.result not in ALLOWED_RESULTS:
        return {"status": "HOLD", "reason": "UNKNOWN_EVIDENCE_RESULT"}
    if evidence.production_sensitive:
        return {"status": "HOLD", "reason": "PRODUCTION_SENSITIVE_EVIDENCE_FORBIDDEN"}
    if not evidence.source_reference:
        return {"status": "HOLD", "reason": "SOURCE_REFERENCE_REQUIRED"}
    if evidence.observed_at_epoch <= 0 or evidence.observed_at_epoch > now_epoch:
        return {"status": "HOLD", "reason": "FUTURE_OR_INVALID_EVIDENCE_TIME"}
    age_seconds = now_epoch - evidence.observed_at_epoch
    if age_seconds > max_age_seconds:
        return {"status": "HOLD", "reason": "STALE_OPERATIONAL_EVIDENCE"}
    if evidence.latency_ms is not None and evidence.latency_ms < 0:
        return {"status": "HOLD", "reason": "INVALID_LATENCY"}
    if evidence.error_rate is not None and not 0 <= evidence.error_rate <= 1:
        return {"status": "HOLD", "reason": "INVALID_ERROR_RATE"}
    if evidence.signal_type == "DEPLOYMENT_STATE":
        if evidence.deployment_state not in ALLOWED_DEPLOYMENT_STATES:
            return {"status": "HOLD", "reason": "DEPLOYMENT_STATE_REQUIRED"}
    elif evidence.deployment_state is not None:
        return {"status": "HOLD", "reason": "DEPLOYMENT_STATE_SCOPE_MISMATCH"}
    if evidence.signal_type == "BACKGROUND_JOB":
        if evidence.job_status not in ALLOWED_JOB_STATES:
            return {"status": "HOLD", "reason": "JOB_STATUS_REQUIRED"}
    elif evidence.job_status is not None:
        return {"status": "HOLD", "reason": "JOB_STATUS_SCOPE_MISMATCH"}

    metrics_decision = None
    if evidence.technical_metrics is not None:
        collector = _load_telemetry_collector()
        metrics = evidence.technical_metrics
        metrics_decision = collector.normalize(
            collector.SourceEvidence(
                workload_id=evidence.project_id,
                evidence_sha=evidence.evidence_sha,
                measured_at=_iso(evidence.observed_at_epoch),
                sample_count=metrics.sample_count,
                success_rate=metrics.success_rate,
                correctness=metrics.correctness,
                safety=metrics.safety,
                p95_latency_ms=metrics.p95_latency_ms,
                source_kind=metrics.source_kind,
                source_reference=evidence.source_reference,
                production_sensitive=False,
            ),
            evidence.evidence_sha,
            now=datetime.fromtimestamp(now_epoch, tz=timezone.utc),
            max_age_hours=max_age_seconds / 3600,
        )
        if metrics_decision.get("status") != "READY":
            return {
                "status": "HOLD",
                "reason": f"TECHNICAL_METRICS_{metrics_decision.get('reason', 'INVALID')}",
            }

    status = "READY"
    reason = "OPERATIONAL_EVIDENCE_READY"
    if evidence.result == "FAIL":
        status, reason = "FAILED", "OPERATIONAL_FAILURE_EVIDENCE"
    elif evidence.result == "HOLD":
        status, reason = "HOLD", "OPERATIONAL_HOLD_EVIDENCE"
    elif metrics_decision and metrics_decision.get("health") == "HUMAN_REVIEW":
        status, reason = "HOLD", "TECHNICAL_METRICS_HUMAN_REVIEW"

    return {
        "status": status,
        "reason": reason,
        "project_id": evidence.project_id,
        "objective_id": evidence.objective_id,
        "signal_type": evidence.signal_type,
        "evidence_sha": evidence.evidence_sha,
        "observed_at_epoch": evidence.observed_at_epoch,
        "expires_at_epoch": evidence.observed_at_epoch + max_age_seconds,
        "source_reference": evidence.source_reference,
        "independent": evidence.independent,
        "metrics_health": metrics_decision.get("health") if metrics_decision else None,
    }


def build_fabric_snapshot(
    registry: dict,
    evidence_items: Iterable[OperationalEvidence],
    *,
    now_epoch: int,
    max_age_seconds: int = 172800,
) -> dict:
    sources = _source_index(registry)
    decisions_by_project: dict[str, list[dict]] = {project_id: [] for project_id in sources}
    unknown_evidence: list[dict] = []

    for evidence in evidence_items:
        source = sources.get(evidence.project_id)
        if source is None:
            unknown_evidence.append({
                "project_id": evidence.project_id,
                "reason": "EVIDENCE_PROJECT_NOT_REGISTERED",
                "source_reference": evidence.source_reference,
            })
            continue
        decisions_by_project[evidence.project_id].append(
            validate_evidence(evidence, source, now_epoch=now_epoch, max_age_seconds=max_age_seconds)
        )

    projects: list[dict] = []
    for project_id, source in sorted(sources.items()):
        if source["mode"] == UNREGISTERED_HOLD:
            projects.append({
                "project_id": project_id,
                "objective_id": source["objective_id"],
                "repository": None,
                "status": "HOLD",
                "truth_candidate": "HOLD",
                "reason": source["hold_reason"],
                "signal_coverage": [],
                "missing_required_signals": sorted(REQUIRED_SIGNAL_TYPES),
                "missing_recommended_signals": sorted(RECOMMENDED_SIGNAL_TYPES),
                "evidence_refs": ["registry:vl/lom-portfolio-runtime/source-registry.json"],
                "independent_validation": False,
            })
            continue

        decisions = decisions_by_project[project_id]
        by_signal: dict[str, list[dict]] = {}
        for decision in decisions:
            by_signal.setdefault(decision.get("signal_type", "INVALID"), []).append(decision)

        contradictory = any(
            len({item.get("status") for item in items}) > 1
            or len({item.get("evidence_sha") for item in items if item.get("evidence_sha")}) > 1
            for signal, items in by_signal.items()
            if signal != "BACKGROUND_JOB"
        )
        coverage = {signal for signal in by_signal if signal in ALLOWED_SIGNAL_TYPES}
        missing_required = REQUIRED_SIGNAL_TYPES - coverage
        missing_recommended = RECOMMENDED_SIGNAL_TYPES - coverage
        flattened = [item for items in by_signal.values() for item in items]
        evidence_refs = sorted({item.get("source_reference") for item in flattened if item.get("source_reference")})
        shas = {item.get("evidence_sha") for item in flattened if item.get("evidence_sha")}
        independent = any(item.get("independent") for item in flattened if item.get("status") == "READY")

        status = "READY"
        truth_candidate = "UNVERIFIED"
        reason = "OPERATIONAL_EVIDENCE_READY"
        if not decisions:
            status, truth_candidate, reason = "HOLD", "HOLD", "OPERATIONAL_EVIDENCE_MISSING"
        elif contradictory:
            status, truth_candidate, reason = "HOLD", "HOLD", "CONTRADICTORY_OPERATIONAL_EVIDENCE"
        elif any(item.get("status") == "FAILED" for item in flattened):
            status, truth_candidate, reason = "FAILED", "FAILED", "OPERATIONAL_FAILURE_PRESENT"
        elif any(item.get("status") == "HOLD" for item in flattened):
            status, truth_candidate, reason = "HOLD", "HOLD", "OPERATIONAL_HOLD_PRESENT"
        elif missing_required:
            status, truth_candidate, reason = "HOLD", "HOLD", "REQUIRED_OPERATIONAL_SIGNAL_MISSING"
        elif len(shas) != 1:
            status, truth_candidate, reason = "HOLD", "HOLD", "EVIDENCE_SHA_SET_MISMATCH"
        elif independent:
            truth_candidate = "VERIFIED"
            reason = "INDEPENDENT_OPERATIONAL_EVIDENCE_READY"
        else:
            reason = "INDEPENDENT_VALIDATION_REQUIRED"

        observed_times = [item.get("observed_at_epoch") for item in flattened if item.get("observed_at_epoch")]
        expiry_times = [item.get("expires_at_epoch") for item in flattened if item.get("expires_at_epoch")]
        projects.append({
            "project_id": project_id,
            "objective_id": source["objective_id"],
            "repository": source["repository"],
            "status": status,
            "truth_candidate": truth_candidate,
            "reason": reason,
            "evidence_sha": next(iter(shas)) if len(shas) == 1 else None,
            "observed_at_epoch": min(observed_times) if observed_times else None,
            "expires_at_epoch": min(expiry_times) if expiry_times else None,
            "signal_coverage": sorted(coverage),
            "missing_required_signals": sorted(missing_required),
            "missing_recommended_signals": sorted(missing_recommended),
            "evidence_refs": evidence_refs,
            "independent_validation": independent,
        })

    overall = "MONITOR"
    if unknown_evidence or any(item["status"] == "FAILED" for item in projects):
        overall = "FAILED" if any(item["status"] == "FAILED" for item in projects) else "HOLD"
    elif any(item["status"] == "HOLD" for item in projects):
        overall = "HOLD"

    fingerprint_payload = {
        "projects": projects,
        "unknown_evidence": unknown_evidence,
    }
    return {
        "schema": FABRIC_SCHEMA,
        "mode": "READ_ONLY_NON_PRODUCTION",
        "overall": overall,
        "projects": projects,
        "unknown_evidence": unknown_evidence,
        "snapshot_fingerprint": _digest(fingerprint_payload),
        "required_signal_types": sorted(REQUIRED_SIGNAL_TYPES),
        "recommended_signal_types": sorted(RECOMMENDED_SIGNAL_TYPES),
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "execution_authority": "NONE",
        "execution_performed": False,
        "cross_repo_write": "DISABLED",
    }


def validate_fabric_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict) or snapshot.get("schema") != FABRIC_SCHEMA:
        return {"status": "HOLD", "reason": "FABRIC_SCHEMA_MISMATCH"}
    if snapshot.get("mode") != "READ_ONLY_NON_PRODUCTION":
        return {"status": "HOLD", "reason": "FABRIC_MODE_INVALID"}
    if snapshot.get("production_authority") != "HUMAN_ONLY":
        return {"status": "HOLD", "reason": "PRODUCTION_AUTHORITY_WEAKENED"}
    if snapshot.get("protected_main_merge") != "HUMAN_ONLY":
        return {"status": "HOLD", "reason": "PROTECTED_MAIN_AUTHORITY_WEAKENED"}
    if snapshot.get("execution_authority") != "NONE" or snapshot.get("execution_performed") is not False:
        return {"status": "HOLD", "reason": "EXECUTION_AUTHORITY_WEAKENED"}
    if snapshot.get("cross_repo_write") != "DISABLED":
        return {"status": "HOLD", "reason": "CROSS_REPO_WRITE_FORBIDDEN"}
    projects = snapshot.get("projects")
    if not isinstance(projects, list) or not projects:
        return {"status": "HOLD", "reason": "FABRIC_PROJECTS_REQUIRED"}
    expected = _digest({
        "projects": projects,
        "unknown_evidence": snapshot.get("unknown_evidence") or [],
    })
    if snapshot.get("snapshot_fingerprint") != expected:
        return {"status": "HOLD", "reason": "FABRIC_FINGERPRINT_MISMATCH"}
    return {"status": "READY", "reason": "FABRIC_SNAPSHOT_VALID"}


def truth_candidate_index(snapshot: dict) -> dict[str, dict]:
    validation = validate_fabric_snapshot(snapshot)
    if validation["status"] != "READY":
        raise ValueError(validation["reason"])
    return {item["project_id"]: dict(item) for item in snapshot["projects"]}
