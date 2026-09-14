from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EvidenceSource:
    workload_id: str
    repository: str
    workflow: str
    visibility: str
    production_sensitive: bool = False


@dataclass(frozen=True)
class WorkflowRunEvidence:
    repository: str
    workflow: str
    run_id: int
    head_sha: str
    status: str
    conclusion: str | None
    updated_at: str
    source_reference: str


@dataclass(frozen=True)
class TechnicalMetricsArtifact:
    evidence_sha: str
    sample_count: int
    success_rate: float
    correctness: float
    safety: float
    p95_latency_ms: int
    source_reference: str


ALLOWED_VISIBILITY = {'public', 'private'}


def access_policy(source: EvidenceSource, *, readonly_credential_available: bool) -> dict:
    if source.production_sensitive:
        return {'status': 'HOLD', 'reason': 'PRODUCTION_SENSITIVE_SOURCE_FORBIDDEN'}
    if source.visibility not in ALLOWED_VISIBILITY:
        return {'status': 'HOLD', 'reason': 'UNKNOWN_REPOSITORY_VISIBILITY'}
    if source.visibility == 'private' and not readonly_credential_available:
        return {'status': 'HOLD', 'reason': 'READ_CREDENTIAL_REQUIRED'}
    return {'status': 'READY', 'reason': 'READ_ONLY_ACCESS_ALLOWED'}


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def validate_run(
    source: EvidenceSource,
    run: WorkflowRunEvidence,
    *,
    expected_sha: str,
    now: datetime | None = None,
    max_age_hours: int = 48,
) -> dict:
    if run.repository != source.repository or run.workflow != source.workflow:
        return {'status': 'HOLD', 'reason': 'SOURCE_IDENTITY_MISMATCH'}
    if run.head_sha != expected_sha:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_SHA_MISMATCH'}
    if run.status != 'completed' or run.conclusion != 'success':
        return {'status': 'HOLD', 'reason': 'WORKFLOW_RUN_NOT_SUCCESSFUL'}
    if run.run_id < 1 or not run.source_reference:
        return {'status': 'HOLD', 'reason': 'RUN_PROVENANCE_REQUIRED'}

    measured_at = _parse_utc(run.updated_at)
    if measured_at is None:
        return {'status': 'HOLD', 'reason': 'INVALID_RUN_TIME'}
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = (current - measured_at).total_seconds() / 3600.0
    if age_hours < 0 or age_hours > max_age_hours:
        return {'status': 'HOLD', 'reason': 'STALE_OR_FUTURE_RUN'}

    return {
        'status': 'READY',
        'reason': 'LIVE_RUN_PROVENANCE_READY',
        'workload_id': source.workload_id,
        'evidence_sha': run.head_sha,
        'source_reference': run.source_reference,
        'run_id': run.run_id,
        'age_hours': round(age_hours, 3),
    }


def promote_metrics(
    source: EvidenceSource,
    run: WorkflowRunEvidence,
    metrics: TechnicalMetricsArtifact | None,
    *,
    expected_sha: str,
    readonly_credential_available: bool,
    now: datetime | None = None,
    max_age_hours: int = 48,
) -> dict:
    access = access_policy(source, readonly_credential_available=readonly_credential_available)
    if access['status'] != 'READY':
        return access

    run_decision = validate_run(source, run, expected_sha=expected_sha, now=now, max_age_hours=max_age_hours)
    if run_decision['status'] != 'READY':
        return run_decision

    if metrics is None:
        return {
            'status': 'HOLD',
            'reason': 'TECHNICAL_METRICS_ARTIFACT_REQUIRED',
            'run_provenance': run_decision,
        }
    if metrics.evidence_sha != run.head_sha:
        return {'status': 'HOLD', 'reason': 'METRICS_SHA_MISMATCH'}
    if metrics.sample_count < 1:
        return {'status': 'HOLD', 'reason': 'SAMPLE_COUNT_REQUIRED'}
    if any(v < 0 or v > 1 for v in (metrics.success_rate, metrics.correctness, metrics.safety)):
        return {'status': 'HOLD', 'reason': 'INVALID_RATE'}
    if metrics.p95_latency_ms < 0 or not metrics.source_reference:
        return {'status': 'HOLD', 'reason': 'METRICS_PROVENANCE_REQUIRED'}

    return {
        'status': 'READY',
        'reason': 'LIVE_TECHNICAL_EVIDENCE_READY',
        'measurement': {
            'workload_id': source.workload_id,
            'evidence_sha': metrics.evidence_sha,
            'measured_at': run.updated_at,
            'sample_count': metrics.sample_count,
            'success_rate': metrics.success_rate,
            'correctness': metrics.correctness,
            'safety': metrics.safety,
            'p95_latency_ms': metrics.p95_latency_ms,
            'source_kind': 'ci_artifact',
            'source_reference': metrics.source_reference,
        },
        'run_provenance': run_decision,
        'mode': 'READ_ONLY_NON_PRODUCTION',
        'cross_repo_write': 'DISABLED',
        'production_action': 'DISABLED',
        'secrets_required_by_adapter': False,
    }
