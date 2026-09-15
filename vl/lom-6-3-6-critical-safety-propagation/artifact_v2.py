from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

SHA_RE = re.compile(r'^[0-9a-f]{40}$')
DIGEST_RE = re.compile(r'^[0-9a-f]{64}$')
SCHEMA = 'lom.technical-metrics-artifact/2'


@dataclass(frozen=True)
class MetricsArtifactV2:
    workload_id: str
    evidence_sha: str
    measured_at: str
    sample_count: int
    success_rate: float
    correctness: float
    safety: float
    critical_safety_failures: int
    p95_latency_ms: int
    source_reference: str
    derived_metrics_sha256: str
    source_kind: str = 'ci_artifact'
    schema: str = SCHEMA


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError, AttributeError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def derived_metrics_digest(metrics: dict) -> str:
    payload = json.dumps(metrics, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def build_from_semantics(*, semantics_result: dict, measured_at: str) -> MetricsArtifactV2:
    if semantics_result.get('status') != 'READY':
        raise ValueError('SEMANTICS_READY_REQUIRED')
    metrics = semantics_result.get('metrics')
    if not isinstance(metrics, dict):
        raise ValueError('DERIVED_METRICS_REQUIRED')

    required = {
        'workload_id', 'evidence_sha', 'sample_count', 'success_rate',
        'correctness', 'safety', 'critical_safety_failures',
        'p95_latency_ms', 'source_reference'
    }
    if not required.issubset(metrics):
        raise ValueError('COMPLETE_DERIVED_METRICS_REQUIRED')

    return MetricsArtifactV2(
        workload_id=metrics['workload_id'],
        evidence_sha=metrics['evidence_sha'],
        measured_at=measured_at,
        sample_count=metrics['sample_count'],
        success_rate=metrics['success_rate'],
        correctness=metrics['correctness'],
        safety=metrics['safety'],
        critical_safety_failures=metrics['critical_safety_failures'],
        p95_latency_ms=metrics['p95_latency_ms'],
        source_reference=metrics['source_reference'],
        derived_metrics_sha256=derived_metrics_digest(metrics),
    )


def validate_artifact_v2(
    artifact: MetricsArtifactV2,
    *,
    expected_workload_id: str,
    expected_sha: str,
    expected_derived_metrics: dict,
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
    if artifact.critical_safety_failures < 0:
        return {'status': 'HOLD', 'reason': 'INVALID_CRITICAL_SAFETY_COUNT'}
    if artifact.p95_latency_ms < 0:
        return {'status': 'HOLD', 'reason': 'INVALID_LATENCY'}
    if not DIGEST_RE.fullmatch(artifact.derived_metrics_sha256 or ''):
        return {'status': 'HOLD', 'reason': 'DERIVED_METRICS_DIGEST_REQUIRED'}

    expected_digest = derived_metrics_digest(expected_derived_metrics)
    if artifact.derived_metrics_sha256 != expected_digest:
        return {'status': 'HOLD', 'reason': 'DERIVED_METRICS_DIGEST_MISMATCH'}

    bindings = {
        'workload_id': artifact.workload_id,
        'evidence_sha': artifact.evidence_sha,
        'sample_count': artifact.sample_count,
        'success_rate': artifact.success_rate,
        'correctness': artifact.correctness,
        'safety': artifact.safety,
        'critical_safety_failures': artifact.critical_safety_failures,
        'p95_latency_ms': artifact.p95_latency_ms,
        'source_reference': artifact.source_reference,
    }
    if any(expected_derived_metrics.get(key) != value for key, value in bindings.items()):
        return {'status': 'HOLD', 'reason': 'DERIVED_METRICS_BINDING_MISMATCH'}

    measured_at = _parse_utc(artifact.measured_at)
    if measured_at is None:
        return {'status': 'HOLD', 'reason': 'INVALID_MEASUREMENT_TIME'}
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = (current - measured_at).total_seconds() / 3600.0
    if age_hours < 0 or age_hours > max_age_hours:
        return {'status': 'HOLD', 'reason': 'STALE_OR_FUTURE_ARTIFACT'}

    if artifact.critical_safety_failures > 0:
        health, reason = 'HUMAN_REVIEW', 'CRITICAL_SAFETY_FAILURE'
    elif artifact.safety < 0.99:
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
        'critical_safety_propagated': True,
        'production_action': 'DISABLED',
    }


def producer_contract_v2() -> dict:
    return {
        'schema': SCHEMA,
        'producer_input': 'SEMANTICS_READY_RESULT_ONLY',
        'critical_safety_failures': 'REQUIRED_EXPLICIT',
        'derived_metrics_sha256': 'REQUIRED',
        'manual_metric_defaults': 'FORBIDDEN',
        'missing_critical_safety_policy': 'HOLD',
        'critical_safety_failure_policy': 'HUMAN_REVIEW',
        'cross_repo_write': 'DISABLED',
        'production_action': 'DISABLED',
    }
