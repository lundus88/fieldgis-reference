from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

SHA40_RE = re.compile(r'^[0-9a-f]{40}$')
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
SCHEMA = 'lom.evidence-lineage/1'


@dataclass(frozen=True)
class LineageRecord:
    workload_id: str
    repository: str
    workflow: str
    run_id: int
    artifact_id: int
    evidence_sha: str
    raw_evidence_sha256: str
    metrics_sha256: str
    replay_manifest_sha256: str
    collected_at: str
    expires_at: str
    run_source_reference: str
    artifact_source_reference: str
    artifact_retrievable: bool = True
    schema: str = SCHEMA


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def custody_payload(record: LineageRecord) -> dict:
    return asdict(record)


def custody_digest(record: LineageRecord) -> str:
    canonical = json.dumps(custody_payload(record), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def validate_lineage(
    record: LineageRecord,
    *,
    expected_workload_id: str,
    expected_repository: str,
    expected_workflow: str,
    expected_evidence_sha: str,
    now: datetime | None = None,
) -> dict:
    if record.schema != SCHEMA:
        return {'status': 'HOLD', 'reason': 'LINEAGE_SCHEMA_MISMATCH'}
    if record.workload_id != expected_workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_MISMATCH'}
    if record.repository != expected_repository or record.workflow != expected_workflow:
        return {'status': 'HOLD', 'reason': 'SOURCE_IDENTITY_MISMATCH'}
    if not SHA40_RE.fullmatch(record.evidence_sha or '') or record.evidence_sha != expected_evidence_sha:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_SHA_MISMATCH'}
    if record.run_id < 1 or record.artifact_id < 1:
        return {'status': 'HOLD', 'reason': 'RUN_ARTIFACT_ID_REQUIRED'}
    for value in (record.raw_evidence_sha256, record.metrics_sha256, record.replay_manifest_sha256):
        if not SHA256_RE.fullmatch(value or ''):
            return {'status': 'HOLD', 'reason': 'INVALID_LINEAGE_DIGEST'}
    if not record.run_source_reference or not record.artifact_source_reference:
        return {'status': 'HOLD', 'reason': 'PROVENANCE_REQUIRED'}
    if not record.artifact_retrievable:
        return {'status': 'HOLD', 'reason': 'ARTIFACT_NOT_RETRIEVABLE'}

    collected = _parse_utc(record.collected_at)
    expires = _parse_utc(record.expires_at)
    if collected is None or expires is None or expires <= collected:
        return {'status': 'HOLD', 'reason': 'INVALID_CUSTODY_TIME'}
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if current < collected:
        return {'status': 'HOLD', 'reason': 'FUTURE_CUSTODY_RECORD'}
    if current >= expires:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_EXPIRED'}

    return {
        'status': 'READY',
        'reason': 'CHAIN_OF_CUSTODY_READY',
        'custody_sha256': custody_digest(record),
        'workload_id': record.workload_id,
        'evidence_sha': record.evidence_sha,
        'run_id': record.run_id,
        'artifact_id': record.artifact_id,
        'mode': 'READ_ONLY_NON_PRODUCTION',
        'cross_repo_write': 'DISABLED',
        'production_action': 'DISABLED',
        'production_authority': 'HUMAN_ONLY',
    }


def validate_chain(
    record: LineageRecord,
    *,
    replay_claim_raw_sha256: str,
    replay_claim_metrics_sha256: str,
    replay_manifest_sha256: str,
    expected_workload_id: str,
    expected_repository: str,
    expected_workflow: str,
    expected_evidence_sha: str,
    now: datetime | None = None,
) -> dict:
    gate = validate_lineage(
        record,
        expected_workload_id=expected_workload_id,
        expected_repository=expected_repository,
        expected_workflow=expected_workflow,
        expected_evidence_sha=expected_evidence_sha,
        now=now,
    )
    if gate['status'] != 'READY':
        return gate
    if record.raw_evidence_sha256 != replay_claim_raw_sha256:
        return {'status': 'HOLD', 'reason': 'RAW_EVIDENCE_LINEAGE_MISMATCH'}
    if record.metrics_sha256 != replay_claim_metrics_sha256:
        return {'status': 'HOLD', 'reason': 'METRICS_LINEAGE_MISMATCH'}
    if record.replay_manifest_sha256 != replay_manifest_sha256:
        return {'status': 'HOLD', 'reason': 'REPLAY_MANIFEST_LINEAGE_MISMATCH'}
    return {**gate, 'reason': 'CHAIN_OF_CUSTODY_VERIFIED'}
