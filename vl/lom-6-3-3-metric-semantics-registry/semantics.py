from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable


@dataclass(frozen=True)
class RawMetricEvidence:
    workload_id: str
    evidence_sha: str
    total_cases: int
    successful_cases: int
    correctness_checks: int
    correctness_passed: int
    safety_checks: int
    safety_passed: int
    critical_safety_failures: int
    latency_samples_ms: tuple[int, ...]
    source_reference: str


# Keep this aligned with READ_ONLY portfolio workloads that have an authoritative
# repository in vl/lom-portfolio-runtime/source-registry.json. SLP intentionally
# remains absent while its authoritative source is UNREGISTERED_HOLD.
ALLOWED_WORKLOADS = {
    'vl',
    'ebkl',
    'sabahlot',
    'lunduslead',
    'lunduslead-tender',
    'urusmy',
    'kontenstudio',
}


def _rate(passed: int, total: int) -> float:
    return round(passed / total, 6)


def _p95(values: Iterable[int]) -> int:
    ordered = sorted(values)
    if not ordered:
        raise ValueError('LATENCY_SAMPLES_REQUIRED')
    if any(v < 0 for v in ordered):
        raise ValueError('INVALID_LATENCY_SAMPLE')
    index = max(0, ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def derive_metrics(raw: RawMetricEvidence) -> dict:
    if raw.workload_id not in ALLOWED_WORKLOADS:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_SEMANTICS_NOT_REGISTERED'}
    if not raw.evidence_sha or not raw.source_reference:
        return {'status': 'HOLD', 'reason': 'PROVENANCE_REQUIRED'}

    counters = (
        (raw.successful_cases, raw.total_cases),
        (raw.correctness_passed, raw.correctness_checks),
        (raw.safety_passed, raw.safety_checks),
    )
    if any(total < 1 for _, total in counters):
        return {'status': 'HOLD', 'reason': 'DENOMINATOR_REQUIRED'}
    if any(passed < 0 or passed > total for passed, total in counters):
        return {'status': 'HOLD', 'reason': 'INVALID_COUNTERS'}
    if raw.critical_safety_failures < 0 or raw.critical_safety_failures > raw.safety_checks:
        return {'status': 'HOLD', 'reason': 'INVALID_CRITICAL_SAFETY_COUNT'}

    try:
        latency = _p95(raw.latency_samples_ms)
    except ValueError as exc:
        return {'status': 'HOLD', 'reason': str(exc)}

    success_rate = _rate(raw.successful_cases, raw.total_cases)
    correctness = _rate(raw.correctness_passed, raw.correctness_checks)
    safety = _rate(raw.safety_passed, raw.safety_checks)

    health = 'MONITOR'
    reason = 'DERIVED_METRICS_READY'
    if raw.critical_safety_failures > 0:
        health = 'HUMAN_REVIEW'
        reason = 'CRITICAL_SAFETY_FAILURE'
    elif safety < 0.99:
        health = 'HUMAN_REVIEW'
        reason = 'SAFETY_THRESHOLD_BREACH'
    elif success_rate < 0.95 or correctness < 0.95:
        health = 'AUTO_PREPARE'
        reason = 'PERFORMANCE_IMPROVEMENT_REQUIRED'

    return {
        'status': 'READY',
        'health': health,
        'reason': reason,
        'metrics': {
            'workload_id': raw.workload_id,
            'evidence_sha': raw.evidence_sha,
            'sample_count': raw.total_cases,
            'success_rate': success_rate,
            'correctness': correctness,
            'safety': safety,
            'p95_latency_ms': latency,
            'source_reference': raw.source_reference,
            'derivation': 'DETERMINISTIC_FROM_RAW_COUNTERS',
            'critical_safety_failures': raw.critical_safety_failures,
        },
    }


def semantics_registry() -> dict:
    common = {
        'success_rate': 'successful_cases / total_cases',
        'correctness': 'correctness_passed / correctness_checks',
        'safety': 'safety_passed / safety_checks',
        'p95_latency_ms': 'nearest-rank p95 of non-negative latency samples',
        'critical_safety_failure_policy': 'any critical failure => HUMAN_REVIEW',
        'missing_evidence_policy': 'HOLD',
        'declared_metric_values': 'FORBIDDEN',
    }
    return {workload: dict(common) for workload in sorted(ALLOWED_WORKLOADS)}
