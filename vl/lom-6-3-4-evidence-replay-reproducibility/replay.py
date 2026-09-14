from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
SCHEMA = 'lom.evidence-replay/1'
DERIVATION_VERSION = 'lom.metric-semantics/1'


@dataclass(frozen=True)
class ReplayClaim:
    workload_id: str
    evidence_sha: str
    raw_evidence_sha256: str
    derivation_version: str
    expected_metrics_sha256: str
    source_reference: str
    schema: str = SCHEMA


def _digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def raw_evidence_digest(raw: dict) -> str:
    return _digest(raw)


def metrics_digest(metrics: dict) -> str:
    return _digest(metrics)


def build_claim(*, workload_id: str, evidence_sha: str, raw: dict, metrics: dict, source_reference: str, derivation_version: str = DERIVATION_VERSION) -> ReplayClaim:
    return ReplayClaim(
        workload_id=workload_id,
        evidence_sha=evidence_sha,
        raw_evidence_sha256=raw_evidence_digest(raw),
        derivation_version=derivation_version,
        expected_metrics_sha256=metrics_digest(metrics),
        source_reference=source_reference,
    )


def validate_claim(claim: ReplayClaim, *, expected_workload_id: str, expected_evidence_sha: str, expected_derivation_version: str = DERIVATION_VERSION) -> dict:
    if claim.schema != SCHEMA:
        return {'status': 'HOLD', 'reason': 'REPLAY_SCHEMA_MISMATCH'}
    if claim.workload_id != expected_workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_MISMATCH'}
    if claim.evidence_sha != expected_evidence_sha:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_SHA_MISMATCH'}
    if claim.derivation_version != expected_derivation_version:
        return {'status': 'HOLD', 'reason': 'DERIVATION_VERSION_MISMATCH'}
    if not SHA256_RE.fullmatch(claim.raw_evidence_sha256 or ''):
        return {'status': 'HOLD', 'reason': 'INVALID_RAW_EVIDENCE_DIGEST'}
    if not SHA256_RE.fullmatch(claim.expected_metrics_sha256 or ''):
        return {'status': 'HOLD', 'reason': 'INVALID_METRICS_DIGEST'}
    if not claim.source_reference:
        return {'status': 'HOLD', 'reason': 'PROVENANCE_REQUIRED'}
    return {'status': 'READY', 'reason': 'REPLAY_CLAIM_READY'}


def replay(claim: ReplayClaim, *, raw: dict, replayed_metrics: dict, expected_workload_id: str, expected_evidence_sha: str, expected_derivation_version: str = DERIVATION_VERSION) -> dict:
    gate = validate_claim(
        claim,
        expected_workload_id=expected_workload_id,
        expected_evidence_sha=expected_evidence_sha,
        expected_derivation_version=expected_derivation_version,
    )
    if gate['status'] != 'READY':
        return gate

    actual_raw_digest = raw_evidence_digest(raw)
    if actual_raw_digest != claim.raw_evidence_sha256:
        return {'status': 'HOLD', 'reason': 'RAW_EVIDENCE_DIGEST_MISMATCH'}

    actual_metrics_digest = metrics_digest(replayed_metrics)
    if actual_metrics_digest != claim.expected_metrics_sha256:
        return {'status': 'HOLD', 'reason': 'REPLAY_METRICS_MISMATCH'}

    return {
        'status': 'READY',
        'reason': 'REPLAY_REPRODUCIBLE',
        'workload_id': claim.workload_id,
        'evidence_sha': claim.evidence_sha,
        'raw_evidence_sha256': actual_raw_digest,
        'metrics_sha256': actual_metrics_digest,
        'derivation_version': claim.derivation_version,
        'mode': 'READ_ONLY_NON_PRODUCTION',
        'cross_repo_write': 'DISABLED',
        'production_action': 'DISABLED',
    }


def manifest(claim: ReplayClaim) -> dict:
    return {
        'schema': SCHEMA,
        'claim': asdict(claim),
        'replay_required': True,
        'mismatch_policy': 'HOLD',
        'derivation_drift_policy': 'HOLD',
        'production_authority': 'HUMAN_ONLY',
    }
