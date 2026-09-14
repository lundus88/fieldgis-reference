from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

ALLOWED_SOURCE_KINDS = {'ci_artifact', 'nonprod_runtime', 'manual_verified'}


@dataclass(frozen=True)
class SourceEvidence:
    workload_id: str
    evidence_sha: str
    measured_at: str
    sample_count: int
    success_rate: float
    correctness: float
    safety: float
    p95_latency_ms: int
    source_kind: str
    source_reference: str
    production_sensitive: bool = False


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def normalize(evidence: SourceEvidence, expected_sha: str, now: datetime | None = None, max_age_hours: int = 48) -> dict:
    if evidence.production_sensitive:
        return {'status': 'HOLD', 'reason': 'PRODUCTION_SENSITIVE_SOURCE_FORBIDDEN'}
    if evidence.source_kind not in ALLOWED_SOURCE_KINDS:
        return {'status': 'HOLD', 'reason': 'SOURCE_KIND_NOT_ALLOWED'}
    if not evidence.source_reference:
        return {'status': 'HOLD', 'reason': 'SOURCE_REFERENCE_REQUIRED'}
    if evidence.evidence_sha != expected_sha:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_SHA_MISMATCH'}
    if evidence.sample_count < 1:
        return {'status': 'HOLD', 'reason': 'SAMPLE_COUNT_REQUIRED'}
    if any(v < 0 or v > 1 for v in (evidence.success_rate, evidence.correctness, evidence.safety)):
        return {'status': 'HOLD', 'reason': 'INVALID_RATE'}
    if evidence.p95_latency_ms < 0:
        return {'status': 'HOLD', 'reason': 'INVALID_LATENCY'}

    measured_at = _parse_utc(evidence.measured_at)
    if measured_at is None:
        return {'status': 'HOLD', 'reason': 'INVALID_MEASUREMENT_TIME'}
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = (current - measured_at).total_seconds() / 3600.0
    if age_hours < 0 or age_hours > max_age_hours:
        return {'status': 'HOLD', 'reason': 'STALE_OR_FUTURE_EVIDENCE'}

    health = 'MONITOR'
    reason = 'TECHNICAL_EVIDENCE_READY'
    if evidence.safety < 0.99:
        health = 'HUMAN_REVIEW'
        reason = 'SAFETY_THRESHOLD_BREACH'
    elif evidence.success_rate < 0.95 or evidence.correctness < 0.95:
        health = 'AUTO_PREPARE'
        reason = 'PERFORMANCE_IMPROVEMENT_REQUIRED'

    return {
        'status': 'READY',
        'health': health,
        'reason': reason,
        'workload_id': evidence.workload_id,
        'evidence_sha': evidence.evidence_sha,
        'sample_count': evidence.sample_count,
        'success_rate': round(evidence.success_rate, 6),
        'correctness': round(evidence.correctness, 6),
        'safety': round(evidence.safety, 6),
        'p95_latency_ms': evidence.p95_latency_ms,
        'source_kind': evidence.source_kind,
        'source_reference': evidence.source_reference,
    }


def missing_source(workload_id: str) -> dict:
    return {'status': 'HOLD', 'reason': 'SOURCE_EVIDENCE_MISSING', 'workload_id': workload_id}
