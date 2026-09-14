from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class WorkloadAnchor:
    workload_id: str
    evidence_sha: str


@dataclass(frozen=True)
class TechnicalMeasurement:
    workload_id: str
    evidence_sha: str
    measured_at: datetime
    sample_count: int
    success_rate: float
    correctness: float
    safety: float
    p95_latency_ms: int
    source_kind: str
    source_reference: str


ALLOWED_SOURCE_KINDS = {'ci_artifact', 'nonprod_runtime', 'manual_verified'}


def validate_measurement(measurement: TechnicalMeasurement, anchor: WorkloadAnchor, *, now: datetime | None = None, max_age_hours: int = 24) -> dict:
    now = now or datetime.now(timezone.utc)
    measured_at = measurement.measured_at.astimezone(timezone.utc)

    if measurement.workload_id != anchor.workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_MISMATCH'}
    if measurement.evidence_sha != anchor.evidence_sha:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_SHA_MISMATCH'}
    if measurement.sample_count < 1:
        return {'status': 'HOLD', 'reason': 'SAMPLE_REQUIRED'}
    if measurement.source_kind not in ALLOWED_SOURCE_KINDS or not measurement.source_reference:
        return {'status': 'HOLD', 'reason': 'PROVENANCE_REQUIRED'}
    if any(value < 0 or value > 1 for value in (measurement.success_rate, measurement.correctness, measurement.safety)):
        return {'status': 'HOLD', 'reason': 'INVALID_RATE'}
    if measurement.p95_latency_ms < 0:
        return {'status': 'HOLD', 'reason': 'INVALID_LATENCY'}

    age_hours = (now - measured_at).total_seconds() / 3600.0
    if age_hours < 0 or age_hours > max_age_hours:
        return {'status': 'HOLD', 'reason': 'STALE_OR_FUTURE_MEASUREMENT'}
    if measurement.safety < 0.99:
        return {'status': 'HUMAN_REVIEW', 'reason': 'SAFETY_THRESHOLD_BREACH'}

    return {
        'status': 'READY',
        'reason': 'MEASUREMENT_VALID',
        'age_hours': round(age_hours, 3),
    }


def aggregate(measurements: Iterable[TechnicalMeasurement], anchor: WorkloadAnchor, *, now: datetime | None = None, max_age_hours: int = 24) -> dict:
    valid = []
    rejected = []
    for measurement in measurements:
        decision = validate_measurement(measurement, anchor, now=now, max_age_hours=max_age_hours)
        if decision['status'] == 'READY':
            valid.append(measurement)
        else:
            rejected.append({'source_reference': measurement.source_reference, **decision})

    if not valid:
        return {'status': 'HOLD', 'reason': 'NO_VALID_MEASUREMENT', 'rejected': rejected}

    total_samples = sum(m.sample_count for m in valid)
    if total_samples <= 0:
        return {'status': 'HOLD', 'reason': 'NO_VALID_SAMPLE', 'rejected': rejected}

    weighted = lambda name: sum(getattr(m, name) * m.sample_count for m in valid) / total_samples
    p95_latency_ms = max(m.p95_latency_ms for m in valid)
    return {
        'status': 'READY',
        'workload_id': anchor.workload_id,
        'evidence_sha': anchor.evidence_sha,
        'sample_count': total_samples,
        'success_rate': round(weighted('success_rate'), 6),
        'correctness': round(weighted('correctness'), 6),
        'safety': round(weighted('safety'), 6),
        'p95_latency_ms': p95_latency_ms,
        'rejected': rejected,
    }


def health(summary: dict) -> dict:
    if summary.get('status') != 'READY':
        return {'health': 'HOLD', 'reason': summary.get('reason', 'MEASUREMENT_NOT_READY')}
    if summary['safety'] < 0.99:
        return {'health': 'HUMAN_REVIEW', 'reason': 'SAFETY_THRESHOLD_BREACH'}
    if summary['success_rate'] < 0.90 or summary['correctness'] < 0.90:
        return {'health': 'AUTO_PREPARE', 'reason': 'PERFORMANCE_IMPROVEMENT_REQUIRED'}
    return {'health': 'MONITOR', 'reason': 'TECHNICAL_HEALTHY'}
