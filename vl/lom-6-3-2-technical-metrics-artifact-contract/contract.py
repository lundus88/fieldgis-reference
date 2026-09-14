from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import re

SHA_RE = re.compile(r'^[0-9a-f]{40}$')
SCHEMA = 'lom.technical-metrics-artifact/1'


@dataclass(frozen=True)
class MetricsArtifact:
    workload_id: str
    evidence_sha: str
    measured_at: str
    sample_count: int
    success_rate: float
    correctness: float
    safety: float
    p95_latency_ms: int
    source_reference: str
    source_kind: str = 'ci_artifact'
    schema: str = SCHEMA


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def validate_artifact(
    artifact: MetricsArtifact,
    *,
    expected_workload_id: str,
    expected_sha: str,
    now: datetime | None = None,
    max_age_hours: int = 48,
) -> dict:
    if artifact.schema != SCHEMA:
        return {'status': 'HOLD', 'reason': 'SCHEMA_MISMATCH'}
    if artifact.workload_id != expected_workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_MISMATCH'}
    if not SHA_RE.fullmatch(artifact.evidence_sha or ''):
        return {'status': 'HOLD', 'reason': 'INVALID_EVIDENCE_SHA'}
    if artifact.evidence_sha != expected_sha:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_SHA_MISMATCH'}
    if artifact.source_kind != 'ci_artifact' or not artifact.source_reference:
        return {'status': 'HOLD', 'reason': 'PROVENANCE_REQUIRED'}
    if artifact.sample_count < 1:
        return {'status': 'HOLD', 'reason': 'SAMPLE_COUNT_REQUIRED'}
    if any(v < 0 or v > 1 for v in (artifact.success_rate, artifact.correctness, artifact.safety)):
        return {'status': 'HOLD', 'reason': 'INVALID_RATE'}
    if artifact.p95_latency_ms < 0:
        return {'status': 'HOLD', 'reason': 'INVALID_LATENCY'}

    measured_at = _parse_utc(artifact.measured_at)
    if measured_at is None:
        return {'status': 'HOLD', 'reason': 'INVALID_MEASUREMENT_TIME'}
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = (current - measured_at).total_seconds() / 3600.0
    if age_hours < 0 or age_hours > max_age_hours:
        return {'status': 'HOLD', 'reason': 'STALE_OR_FUTURE_ARTIFACT'}

    if artifact.safety < 0.99:
        health, reason = 'HUMAN_REVIEW', 'SAFETY_THRESHOLD_BREACH'
    elif artifact.success_rate < 0.95 or artifact.correctness < 0.95:
        health, reason = 'AUTO_PREPARE', 'PERFORMANCE_IMPROVEMENT_REQUIRED'
    else:
        health, reason = 'MONITOR', 'TECHNICAL_METRICS_READY'

    return {
        'status': 'READY',
        'health': health,
        'reason': reason,
        'age_hours': round(age_hours, 3),
        'artifact': asdict(artifact),
    }


def build_template(*, workload_id: str, evidence_sha: str, measured_at: str, source_reference: str) -> dict:
    return asdict(MetricsArtifact(
        workload_id=workload_id,
        evidence_sha=evidence_sha,
        measured_at=measured_at,
        sample_count=1,
        success_rate=1.0,
        correctness=1.0,
        safety=1.0,
        p95_latency_ms=0,
        source_reference=source_reference,
    ))


def render_template_json(**kwargs) -> str:
    return json.dumps(build_template(**kwargs), indent=2, sort_keys=True) + '\n'


def producer_contract() -> dict:
    return {
        'artifact_name': 'lom-technical-metrics-${GITHUB_SHA}',
        'artifact_file': 'lom-technical-metrics.json',
        'bind_to': 'github.sha',
        'upload': 'actions/upload-artifact@v4',
        'permissions': {'contents': 'read'},
        'production_credentials': 'FORBIDDEN',
        'fabricated_metrics': 'FORBIDDEN',
        'missing_metric_policy': 'HOLD',
        'cross_repo_write': 'DISABLED',
    }
