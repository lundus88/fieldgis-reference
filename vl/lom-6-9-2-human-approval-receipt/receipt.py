from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import hmac
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
    identity_subject: str
    issuer_id: str
    decision: str
    nonce: str
    issued_at: str
    expires_at: str
    source_reference: str
    signature_sha256: str = ''


def _parse_time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _unsigned_payload(receipt: ApprovalReceipt) -> dict:
    return {
        'schema': 'lom.human-approval-receipt/2',
        'workload_id': receipt.workload_id,
        'candidate_sha': receipt.candidate_sha,
        'decision_package_sha256': receipt.decision_package_sha256,
        'actor_id': receipt.actor_id,
        'identity_subject': receipt.identity_subject,
        'issuer_id': receipt.issuer_id,
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


def _signature_input(receipt: ApprovalReceipt) -> bytes:
    return json.dumps(_unsigned_payload(receipt), sort_keys=True, separators=(',', ':')).encode('utf-8')


def sign_receipt(receipt: ApprovalReceipt, *, issuer_key: bytes) -> ApprovalReceipt:
    if not issuer_key:
        raise ValueError('ISSUER_KEY_REQUIRED')
    signature = hmac.new(issuer_key, _signature_input(receipt), hashlib.sha256).hexdigest()
    return replace(receipt, signature_sha256=signature)


def receipt_digest(receipt: ApprovalReceipt) -> str:
    payload = {
        **_unsigned_payload(receipt),
        'signature_sha256': receipt.signature_sha256,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def validate_receipt(
    receipt: ApprovalReceipt,
    *,
    expected_candidate_sha: str,
    expected_decision_package_sha256: str,
    now: datetime,
    trusted_issuer_keys: dict[str, bytes],
    trusted_actor_subjects: dict[str, str],
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
    if not receipt.identity_subject.strip():
        return {'status': 'HOLD', 'reason': 'IDENTITY_SUBJECT_REQUIRED'}
    expected_subject = trusted_actor_subjects.get(receipt.actor_id)
    if expected_subject is None:
        return {'status': 'HOLD', 'reason': 'UNTRUSTED_HUMAN_ACTOR'}
    if not hmac.compare_digest(receipt.identity_subject, expected_subject):
        return {'status': 'HOLD', 'reason': 'HUMAN_IDENTITY_BINDING_MISMATCH'}
    issuer_key = trusted_issuer_keys.get(receipt.issuer_id)
    if not receipt.issuer_id.strip() or issuer_key is None:
        return {'status': 'HOLD', 'reason': 'UNTRUSTED_IDENTITY_ISSUER'}
    if not DIGEST_RE.fullmatch(receipt.signature_sha256 or ''):
        return {'status': 'HOLD', 'reason': 'SIGNATURE_REQUIRED'}
    expected_signature = hmac.new(issuer_key, _signature_input(receipt), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(receipt.signature_sha256, expected_signature):
        return {'status': 'HOLD', 'reason': 'SIGNATURE_INVALID'}
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
    return {
        'schema': 'lom.human-approval-receipt-package/2',
        'receipt': {**_unsigned_payload(receipt), 'signature_sha256': receipt.signature_sha256},
        'receipt_sha256': receipt_digest(receipt),
        'cryptographic_signature_required': True,
        'trusted_issuer_required': True,
        'trusted_human_identity_binding_required': True,
        'single_use_nonce_required': True,
        'bound_to_exact_candidate': True,
        'bound_to_exact_decision_package': True,
        'human_authority_required': True,
        'auto_approval': 'DISABLED',
        'auto_merge': 'DISABLED',
        'production_execution': 'DISABLED',
        'external_action_execution': 'DISABLED',
    }
