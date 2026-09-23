from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable

HEALTH_SCHEMA = "lom.system-health-drift/1"
LEDGER_SCHEMA = "lom.cross-system-evidence-ledger/1"
SENTINEL_SCHEMA = "lom.regression-sentinel/1"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

STATUS_PRIORITY = {
    "HEALTHY": 0,
    "DEGRADED": 10,
    "HOLD": 20,
    "ACTION_REQUIRED": 30,
}

ALLOWED_CI = {"PASS", "FAIL", "UNKNOWN"}
ALLOWED_RUNTIME = {"HEALTHY", "DEGRADED", "FAILED", "UNKNOWN"}
ALLOWED_PRODUCTION_POLICIES = {"LOCKED", "TRACK_MAIN", "NOT_APPLICABLE"}
ALLOWED_REGRESSION = {"PASS", "FAIL", "SKIP"}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def _status_max(*statuses: str) -> str:
    return max(statuses, key=lambda item: STATUS_PRIORITY[item])


def _valid_sha(value: str | None) -> bool:
    return bool(value and SHA_RE.fullmatch(value))


@dataclass(frozen=True)
class ProjectObservation:
    project_id: str
    repository: str
    main_sha: str
    observed_at_epoch: int
    max_age_seconds: int
    ci_sha: str
    ci_status: str
    runtime_status: str
    evidence_refs: tuple[str, ...]
    preview_sha: str | None = None
    production_sha: str | None = None
    preview_required: bool = False
    production_policy: str = "LOCKED"
    database_fingerprint: str | None = None
    expected_database_fingerprint: str | None = None


@dataclass(frozen=True)
class RegressionResult:
    project_id: str
    journey_id: str
    critical: bool
    status: str
    exact_sha: str
    evidence_ref: str
    observed_at_epoch: int


class CrossSystemEvidenceLedger:
    """Durable append-only hash-chain ledger.

    P0 deliberately has no update/delete API. Every append verifies the existing
    chain before writing. This is evidence integrity, not legal/non-repudiation
    signing; stronger external sealing can be layered later.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
        return records

    def verify(self) -> dict[str, Any]:
        records = self._read()
        prev_hash = "GENESIS"
        for expected_sequence, record in enumerate(records, start=1):
            if record.get("schema") != LEDGER_SCHEMA:
                return {"status": "HOLD", "reason": "LEDGER_SCHEMA_MISMATCH"}
            if record.get("sequence") != expected_sequence:
                return {"status": "HOLD", "reason": "LEDGER_SEQUENCE_MISMATCH"}
            if record.get("prev_hash") != prev_hash:
                return {"status": "HOLD", "reason": "LEDGER_CHAIN_MISMATCH"}
            candidate = dict(record)
            stored_hash = candidate.pop("record_hash", None)
            if not stored_hash or digest(candidate) != stored_hash:
                return {"status": "HOLD", "reason": "LEDGER_HASH_MISMATCH"}
            prev_hash = stored_hash
        return {
            "status": "READY",
            "reason": "LEDGER_VALID",
            "record_count": len(records),
            "head_hash": prev_hash,
        }

    def append(
        self,
        *,
        record_type: str,
        project_id: str,
        payload: dict[str, Any],
        evidence_refs: Iterable[str],
        observed_at_epoch: int,
    ) -> dict[str, Any]:
        verification = self.verify()
        if verification["status"] != "READY":
            raise ValueError(verification["reason"])
        refs = sorted({str(ref).strip() for ref in evidence_refs if str(ref).strip()})
        if not record_type or not project_id or observed_at_epoch <= 0 or not refs:
            raise ValueError("LEDGER_EVIDENCE_INCOMPLETE")

        sequence = verification["record_count"] + 1
        record = {
            "schema": LEDGER_SCHEMA,
            "sequence": sequence,
            "record_type": record_type,
            "project_id": project_id,
            "payload": payload,
            "evidence_refs": refs,
            "observed_at_epoch": observed_at_epoch,
            "prev_hash": verification["head_hash"],
        }
        record["record_hash"] = digest(record)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return dict(record)


def detect_deployment_drift(observation: ProjectObservation) -> dict[str, Any]:
    """Compare main, preview and Production without granting deployment authority."""

    drifts: list[dict[str, str]] = []
    status = "HEALTHY"

    if observation.preview_required:
        if not _valid_sha(observation.preview_sha):
            status = _status_max(status, "HOLD")
            drifts.append({"code": "PREVIEW_EVIDENCE_MISSING", "severity": "HOLD"})
        elif observation.preview_sha != observation.main_sha:
            status = _status_max(status, "DEGRADED")
            drifts.append({"code": "PREVIEW_DRIFT", "severity": "DEGRADED"})

    if observation.production_policy not in ALLOWED_PRODUCTION_POLICIES:
        return {
            "schema": HEALTH_SCHEMA,
            "status": "HOLD",
            "reason": "UNKNOWN_PRODUCTION_POLICY",
            "drifts": [{"code": "UNKNOWN_PRODUCTION_POLICY", "severity": "HOLD"}],
            "production_authority": "HUMAN_ONLY",
        }

    if observation.production_policy == "TRACK_MAIN":
        if not _valid_sha(observation.production_sha):
            status = _status_max(status, "HOLD")
            drifts.append({"code": "PRODUCTION_EVIDENCE_MISSING", "severity": "HOLD"})
        elif observation.production_sha != observation.main_sha:
            status = _status_max(status, "ACTION_REQUIRED")
            drifts.append({"code": "PRODUCTION_DRIFT", "severity": "ACTION_REQUIRED"})
    elif observation.production_policy == "LOCKED":
        if not _valid_sha(observation.production_sha):
            status = _status_max(status, "DEGRADED")
            drifts.append({"code": "PRODUCTION_LOCKED_NO_DEPLOYMENT_EVIDENCE", "severity": "DEGRADED"})
        elif observation.production_sha != observation.main_sha:
            status = _status_max(status, "DEGRADED")
            drifts.append({"code": "EXPECTED_PRODUCTION_HOLD_DRIFT", "severity": "DEGRADED"})

    return {
        "schema": HEALTH_SCHEMA,
        "status": status,
        "reason": drifts[0]["code"] if drifts else "DEPLOYMENT_PARITY_OK",
        "drifts": drifts,
        "production_policy": observation.production_policy,
        "production_authority": "HUMAN_ONLY",
        "deployment_mutation": "DISABLED",
    }


def assess_project_health(observation: ProjectObservation, *, now_epoch: int) -> dict[str, Any]:
    reasons: list[str] = []
    status = "HEALTHY"

    if not observation.project_id or not observation.repository:
        return _hold(observation.project_id, "PROJECT_IDENTITY_REQUIRED")
    if not _valid_sha(observation.main_sha):
        return _hold(observation.project_id, "MAIN_SHA_INVALID")
    if observation.max_age_seconds <= 0 or observation.observed_at_epoch <= 0:
        return _hold(observation.project_id, "OBSERVATION_TIME_INVALID")
    if observation.observed_at_epoch > now_epoch:
        return _hold(observation.project_id, "OBSERVATION_FROM_FUTURE")
    if now_epoch - observation.observed_at_epoch > observation.max_age_seconds:
        return _hold(observation.project_id, "OBSERVATION_STALE")
    if not observation.evidence_refs:
        return _hold(observation.project_id, "EVIDENCE_REFS_REQUIRED")

    if observation.ci_status not in ALLOWED_CI:
        return _hold(observation.project_id, "CI_STATUS_UNKNOWN")
    if not _valid_sha(observation.ci_sha):
        return _hold(observation.project_id, "CI_SHA_INVALID")
    if observation.ci_sha != observation.main_sha:
        status = _status_max(status, "HOLD")
        reasons.append("CI_NOT_EXACT_MAIN")
    if observation.ci_status == "FAIL":
        status = _status_max(status, "ACTION_REQUIRED")
        reasons.append("CI_FAILURE")
    elif observation.ci_status == "UNKNOWN":
        status = _status_max(status, "HOLD")
        reasons.append("CI_EVIDENCE_UNKNOWN")

    if observation.runtime_status not in ALLOWED_RUNTIME:
        return _hold(observation.project_id, "RUNTIME_STATUS_UNKNOWN")
    if observation.runtime_status == "FAILED":
        status = _status_max(status, "ACTION_REQUIRED")
        reasons.append("RUNTIME_FAILURE")
    elif observation.runtime_status == "UNKNOWN":
        status = _status_max(status, "HOLD")
        reasons.append("RUNTIME_EVIDENCE_UNKNOWN")
    elif observation.runtime_status == "DEGRADED":
        status = _status_max(status, "DEGRADED")
        reasons.append("RUNTIME_DEGRADED")

    deployment = detect_deployment_drift(observation)
    status = _status_max(status, deployment["status"])
    reasons.extend(item["code"] for item in deployment["drifts"])

    expected_db = observation.expected_database_fingerprint
    observed_db = observation.database_fingerprint
    if expected_db is not None:
        if not observed_db:
            status = _status_max(status, "HOLD")
            reasons.append("DATABASE_EVIDENCE_MISSING")
        elif observed_db != expected_db:
            status = _status_max(status, "HOLD")
            reasons.append("DATABASE_DRIFT")

    body = {
        "schema": HEALTH_SCHEMA,
        "project_id": observation.project_id,
        "repository": observation.repository,
        "main_sha": observation.main_sha,
        "status": status,
        "reasons": sorted(set(reasons)) if reasons else ["ALL_REQUIRED_SIGNALS_HEALTHY"],
        "deployment": deployment,
        "evidence_refs": sorted(set(observation.evidence_refs)),
        "observed_at_epoch": observation.observed_at_epoch,
        "fresh_until_epoch": observation.observed_at_epoch + observation.max_age_seconds,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "production_mutation": "DISABLED",
    }
    return {**body, "assessment_digest": digest(body)}


def _hold(project_id: str, reason: str) -> dict[str, Any]:
    body = {
        "schema": HEALTH_SCHEMA,
        "project_id": project_id or None,
        "status": "HOLD",
        "reasons": [reason],
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "production_mutation": "DISABLED",
    }
    return {**body, "assessment_digest": digest(body)}


def evaluate_regression_sentinel(
    *,
    project_id: str,
    expected_main_sha: str,
    required_journeys: Iterable[str],
    results: Iterable[RegressionResult],
    now_epoch: int,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not project_id or not _valid_sha(expected_main_sha) or max_age_seconds <= 0:
        return _sentinel_hold(project_id, "SENTINEL_INPUT_INVALID")

    items = list(results)
    required = {str(item).strip() for item in required_journeys if str(item).strip()}
    if not required:
        return _sentinel_hold(project_id, "REQUIRED_JOURNEYS_EMPTY")

    by_journey: dict[str, RegressionResult] = {}
    status = "HEALTHY"
    reasons: list[str] = []

    for item in items:
        if item.project_id != project_id:
            status = _status_max(status, "HOLD")
            reasons.append("REGRESSION_SCOPE_MISMATCH")
            continue
        if item.status not in ALLOWED_REGRESSION or not item.evidence_ref:
            status = _status_max(status, "HOLD")
            reasons.append("REGRESSION_EVIDENCE_INVALID")
            continue
        if item.observed_at_epoch <= 0 or item.observed_at_epoch > now_epoch:
            status = _status_max(status, "HOLD")
            reasons.append("REGRESSION_TIME_INVALID")
            continue
        if now_epoch - item.observed_at_epoch > max_age_seconds:
            status = _status_max(status, "HOLD")
            reasons.append("REGRESSION_STALE")
        if item.exact_sha != expected_main_sha:
            status = _status_max(status, "HOLD")
            reasons.append("REGRESSION_NOT_EXACT_MAIN")
        if item.journey_id in by_journey:
            status = _status_max(status, "HOLD")
            reasons.append("DUPLICATE_JOURNEY_RESULT")
        by_journey[item.journey_id] = item

        if item.status == "FAIL":
            severity = "ACTION_REQUIRED" if item.critical else "DEGRADED"
            status = _status_max(status, severity)
            reasons.append("CRITICAL_JOURNEY_FAILED" if item.critical else "NONCRITICAL_JOURNEY_FAILED")
        elif item.status == "SKIP":
            severity = "HOLD" if item.critical else "DEGRADED"
            status = _status_max(status, severity)
            reasons.append("CRITICAL_JOURNEY_SKIPPED" if item.critical else "NONCRITICAL_JOURNEY_SKIPPED")

    missing = sorted(required - set(by_journey))
    if missing:
        status = _status_max(status, "HOLD")
        reasons.append("REQUIRED_JOURNEY_MISSING")

    body = {
        "schema": SENTINEL_SCHEMA,
        "project_id": project_id,
        "expected_main_sha": expected_main_sha,
        "status": status,
        "reasons": sorted(set(reasons)) if reasons else ["ALL_REQUIRED_JOURNEYS_PASS"],
        "required_journeys": sorted(required),
        "missing_journeys": missing,
        "results": [asdict(item) for item in sorted(items, key=lambda x: x.journey_id)],
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "automatic_production_rollback": "DISABLED",
    }
    return {**body, "sentinel_digest": digest(body)}


def _sentinel_hold(project_id: str, reason: str) -> dict[str, Any]:
    body = {
        "schema": SENTINEL_SCHEMA,
        "project_id": project_id or None,
        "status": "HOLD",
        "reasons": [reason],
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "automatic_production_rollback": "DISABLED",
    }
    return {**body, "sentinel_digest": digest(body)}


def build_portfolio_snapshot(
    assessments: Iterable[dict[str, Any]],
    sentinels: Iterable[dict[str, Any]],
    *,
    expected_project_ids: Iterable[str] = (),
) -> dict[str, Any]:
    health_items = [item for item in assessments if item.get("project_id")]
    sentinel_items = [item for item in sentinels if item.get("project_id")]
    health = {item["project_id"]: item for item in health_items}
    regression = {item["project_id"]: item for item in sentinel_items}
    duplicate_health = len(health) != len(health_items)
    duplicate_regression = len(regression) != len(sentinel_items)

    expected = {str(item).strip() for item in expected_project_ids if str(item).strip()}
    project_ids = sorted(expected | set(health) | set(regression))
    projects: list[dict[str, Any]] = []
    overall = "HEALTHY" if project_ids else "HOLD"

    for project_id in project_ids:
        h = health.get(project_id)
        s = regression.get(project_id)
        raw_h_status = h.get("status") if h else "HOLD"
        raw_s_status = s.get("status") if s else "HOLD"
        h_status = raw_h_status if raw_h_status in STATUS_PRIORITY else "HOLD"
        s_status = raw_s_status if raw_s_status in STATUS_PRIORITY else "HOLD"
        combined = _status_max(h_status, s_status)
        overall = _status_max(overall, combined)

        reasons: list[str] = []
        if h is None:
            reasons.append("HEALTH_ASSESSMENT_MISSING")
        elif raw_h_status not in STATUS_PRIORITY:
            reasons.append("HEALTH_STATUS_UNKNOWN")
        if s is None:
            reasons.append("REGRESSION_SENTINEL_MISSING")
        elif raw_s_status not in STATUS_PRIORITY:
            reasons.append("REGRESSION_STATUS_UNKNOWN")

        projects.append({
            "project_id": project_id,
            "status": combined,
            "health_status": h_status,
            "regression_status": s_status,
            "reasons": reasons or ["PROJECT_EVIDENCE_COMPLETE"],
            "health_digest": h.get("assessment_digest") if h else None,
            "sentinel_digest": s.get("sentinel_digest") if s else None,
        })

    integrity_reasons: list[str] = []
    if duplicate_health:
        integrity_reasons.append("DUPLICATE_HEALTH_ASSESSMENT")
    if duplicate_regression:
        integrity_reasons.append("DUPLICATE_REGRESSION_SENTINEL")
    if duplicate_health or duplicate_regression:
        overall = _status_max(overall, "HOLD")

    body = {
        "schema": "lom.portfolio-health/1",
        "overall": overall,
        "projects": projects,
        "expected_project_ids": sorted(expected),
        "integrity_reasons": integrity_reasons,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "execution_authority": "NONE",
    }
    return {**body, "portfolio_digest": digest(body)}
