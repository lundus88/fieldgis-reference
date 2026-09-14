from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

SHA_RE = re.compile(r'^[0-9a-f]{40}$')
DIGEST_RE = re.compile(r'^[0-9a-f]{64}$')
NONCE_RE = re.compile(r'^[A-Za-z0-9._:-]{16,128}$')
ALLOWED_DECISIONS = {'APPROVE', 'REJECT', 'REQUEST_CHANGES'}


@dataclass(frozen=True)
class ApprovalReceipt:
    workload_id: str
    candidate_sha: str
    decision_package_sha256: str
    actor_id: str
    decision: str
    nonce: str
    issued_at: str
    expires_at: str
    source_reference: str


def _parse_time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _canonical_payload(receipt: ApprovalReceipt) -> dict:
    return {
        'schema': 'lom.human-approval-receipt/1',
        'workload_id': receipt.workload_id,
        'candidate_sha': receipt.candidate_sha,
        'decision_package_sha256': receipt.decision_package_sha256,
        'actor_id': receipt.actor_id,
        'decision': receipt.decision,
        'nonce': receipt.nonce,
        'issued_at': receipt.issued_at,
        'expires_at': receipt.expires_at,
        'source_reference': receipt.source_reference,
        'human_authority_required': True,
        'auto_approval': 'DISABLED',
        'replay': 'DENY',
        'production_execution': 'DISABLED',
    }


def receipt_digest(receipt: ApprovalReceipt) -> str:
    payload = json.dumps(_canonical_payload(receipt), sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def validate_receipt(
    receipt: ApprovalReceipt,
    *,
    expected_candidate_sha: str,
    expected_decision_package_sha256: str,
    now: datetime,
    consumed_nonces: set[str] | frozenset[str] = frozenset(),
) -> dict:
    if not receipt.workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_ID_REQUIRED'}
    if not SHA_RE.fullmatch(receipt.candidate_sha or ''):
        return {'status': 'HOLD', 'reason': 'EXACT_CANDIDATE_SHA_REQUIRED'}
    if not DIGEST_RE.fullmatch(receipt.decision_package_sha256 or ''):
        return {'status': 'HOLD', 'reason': 'DECISION_PACKAGE_DIGEST_REQUIRED'}
    if receipt.candidate_sha != expected_candidate_sha:
        return {'status': 'HOLD', 'reason': 'CANDIDATE_SHA_MISMATCH'}
    if receipt.decision_package_sha256 != expected_decision_package_sha256:
        return {'status': 'HOLD', 'reason': 'DECISION_PACKAGE_DIGEST_MISMATCH'}
    if not receipt.actor_id.strip():
        return {'status': 'HOLD', 'reason': 'ACTOR_ID_REQUIRED'}
    if receipt.decision not in ALLOWED_DECISIONS:
        return {'status': 'HOLD', 'reason': 'UNKNOWN_DECISION'}
    if not NONCE_RE.fullmatch(receipt.nonce or ''):
        return {'status': 'HOLD', 'reason': 'VALID_NONCE_REQUIRED'}
    if receipt.nonce in consumed_nonces:
        return {'status': 'HOLD', 'reason': 'NONCE_ALREADY_CONSUMED'}
    if not receipt.source_reference.strip():
        return {'status': 'HOLD', 'reason': 'SOURCE_REFERENCE_REQUIRED'}

    issued_at = _parse_time(receipt.issued_at)
    expires_at = _parse_time(receipt.expires_at)
    if issued_at is None or expires_at is None:
        return {'status': 'HOLD', 'reason': 'VALID_TIMESTAMPS_REQUIRED'}
    now_utc = now.astimezone(timezone.utc)
    if issued_at > now_utc:
        return {'status': 'HOLD', 'reason': 'ISSUED_AT_IN_FUTURE'}
    if expires_at <= issued_at:
        return {'status': 'HOLD', 'reason': 'INVALID_EXPIRY_WINDOW'}
    if now_utc >= expires_at:
        return {'status': 'HOLD', 'reason': 'APPROVAL_RECEIPT_EXPIRED'}

    if receipt.decision == 'APPROVE':
        return {'status': 'APPROVED_FOR_BOUND_ACTION', 'reason': 'HUMAN_APPROVAL_RECEIPT_VALID'}
    if receipt.decision == 'REJECT':
        return {'status': 'REJECTED', 'reason': 'HUMAN_REJECTION_RECEIPT_VALID'}
    return {'status': 'REQUEST_CHANGES', 'reason': 'HUMAN_CHANGE_REQUEST_RECEIPT_VALID'}


def build_receipt_package(receipt: ApprovalReceipt) -> dict:
    payload = _canonical_payload(receipt)
    digest = receipt_digest(receipt)
    return {
        'schema': 'lom.human-approval-receipt-package/1',
        'receipt': payload,
        'receipt_sha256': digest,
        'single_use_nonce_required': True,
        'bound_to_exact_candidate': True,
        'bound_to_exact_decision_package': True,
        'human_authority_required': True,
        'auto_approval': 'DISABLED',
        'auto_merge': 'DISABLED',
        'production_execution': 'DISABLED',
        'external_action_execution': 'DISABLED',
    }
