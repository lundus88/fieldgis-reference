from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

SHA_RE = re.compile(r'^[0-9a-f]{40}$')
DIGEST_RE = re.compile(r'^[0-9a-f]{64}$')
NONCE_RE = re.compile(r'^[A-Za-z0-9._:-]{16,128}$')
IDEMPOTENCY_RE = re.compile(r'^[A-Za-z0-9._:-]{16,128}$')
ALLOWED_RECEIPT_STATUS = {'APPROVED_FOR_BOUND_ACTION'}


@dataclass(frozen=True)
class ConsumptionRequest:
    workload_id: str
    candidate_sha: str
    receipt_sha256: str
    receipt_nonce: str
    receipt_status: str
    action: str
    idempotency_key: str
    consumed_at: str
    source_reference: str


@dataclass(frozen=True)
class LedgerEntry:
    workload_id: str
    candidate_sha: str
    receipt_sha256: str
    receipt_nonce: str
    action: str
    idempotency_key: str
    consumed_at: str
    source_reference: str
    previous_record_sha256: str | None
    record_sha256: str


def _parse_time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _entry_payload(req: ConsumptionRequest, previous_record_sha256: str | None) -> dict:
    return {
        'schema': 'lom.approval-consumption-ledger/2',
        'workload_id': req.workload_id,
        'candidate_sha': req.candidate_sha,
        'receipt_sha256': req.receipt_sha256,
        'receipt_nonce': req.receipt_nonce,
        'action': req.action,
        'idempotency_key': req.idempotency_key,
        'consumed_at': req.consumed_at,
        'source_reference': req.source_reference,
        'previous_record_sha256': previous_record_sha256,
        'append_only': True,
        'single_use_receipt': True,
        'idempotent_retry_only': True,
        'production_execution': 'DISABLED',
    }


def record_digest(req: ConsumptionRequest, previous_record_sha256: str | None = None) -> str:
    raw = json.dumps(
        _entry_payload(req, previous_record_sha256),
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _request_from_entry(entry: LedgerEntry) -> ConsumptionRequest:
    return ConsumptionRequest(
        workload_id=entry.workload_id,
        candidate_sha=entry.candidate_sha,
        receipt_sha256=entry.receipt_sha256,
        receipt_nonce=entry.receipt_nonce,
        receipt_status='APPROVED_FOR_BOUND_ACTION',
        action=entry.action,
        idempotency_key=entry.idempotency_key,
        consumed_at=entry.consumed_at,
        source_reference=entry.source_reference,
    )


def verify_ledger_chain(existing_entries: tuple[LedgerEntry, ...]) -> dict:
    expected_previous: str | None = None
    for index, entry in enumerate(existing_entries):
        if not DIGEST_RE.fullmatch(entry.record_sha256 or ''):
            return {'status': 'HOLD', 'reason': 'INVALID_EXISTING_LEDGER_ENTRY', 'index': index}
        if entry.previous_record_sha256 != expected_previous:
            return {'status': 'HOLD', 'reason': 'LEDGER_CHAIN_BROKEN', 'index': index}
        recomputed = record_digest(_request_from_entry(entry), entry.previous_record_sha256)
        if entry.record_sha256 != recomputed:
            return {'status': 'HOLD', 'reason': 'LEDGER_RECORD_DIGEST_MISMATCH', 'index': index}
        expected_previous = entry.record_sha256
    return {'status': 'READY', 'reason': 'LEDGER_CHAIN_VALID', 'tail_sha256': expected_previous}


def _same_bound_operation(req: ConsumptionRequest, entry: LedgerEntry) -> bool:
    return (
        req.workload_id == entry.workload_id
        and req.candidate_sha == entry.candidate_sha
        and req.receipt_sha256 == entry.receipt_sha256
        and req.receipt_nonce == entry.receipt_nonce
        and req.action == entry.action
        and req.idempotency_key == entry.idempotency_key
    )


def validate_consumption(
    req: ConsumptionRequest,
    *,
    existing_entries: tuple[LedgerEntry, ...] = (),
    now: datetime,
) -> dict:
    if not req.workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_ID_REQUIRED'}
    if not SHA_RE.fullmatch(req.candidate_sha or ''):
        return {'status': 'HOLD', 'reason': 'EXACT_CANDIDATE_SHA_REQUIRED'}
    if not DIGEST_RE.fullmatch(req.receipt_sha256 or ''):
        return {'status': 'HOLD', 'reason': 'RECEIPT_DIGEST_REQUIRED'}
    if not NONCE_RE.fullmatch(req.receipt_nonce or ''):
        return {'status': 'HOLD', 'reason': 'VALID_RECEIPT_NONCE_REQUIRED'}
    if req.receipt_status not in ALLOWED_RECEIPT_STATUS:
        return {'status': 'HOLD', 'reason': 'APPROVED_RECEIPT_REQUIRED'}
    if not req.action.strip():
        return {'status': 'HOLD', 'reason': 'ACTION_REQUIRED'}
    if not IDEMPOTENCY_RE.fullmatch(req.idempotency_key or ''):
        return {'status': 'HOLD', 'reason': 'VALID_IDEMPOTENCY_KEY_REQUIRED'}
    if not req.source_reference.strip():
        return {'status': 'HOLD', 'reason': 'SOURCE_REFERENCE_REQUIRED'}
    consumed_at = _parse_time(req.consumed_at)
    if consumed_at is None:
        return {'status': 'HOLD', 'reason': 'VALID_CONSUMED_AT_REQUIRED'}
    now_utc = now.astimezone(timezone.utc)
    if consumed_at > now_utc:
        return {'status': 'HOLD', 'reason': 'CONSUMED_AT_IN_FUTURE'}

    chain = verify_ledger_chain(existing_entries)
    if chain['status'] != 'READY':
        return chain

    for entry in existing_entries:
        if entry.receipt_sha256 == req.receipt_sha256 or entry.receipt_nonce == req.receipt_nonce:
            if _same_bound_operation(req, entry):
                return {'status': 'IDEMPOTENT_NOOP', 'reason': 'ALREADY_CONSUMED_SAME_BOUND_OPERATION'}
            return {'status': 'HOLD', 'reason': 'RECEIPT_REPLAY_OR_REBIND_ATTEMPT'}
        if entry.idempotency_key == req.idempotency_key:
            if _same_bound_operation(req, entry):
                return {'status': 'IDEMPOTENT_NOOP', 'reason': 'ALREADY_CONSUMED_SAME_BOUND_OPERATION'}
            return {'status': 'HOLD', 'reason': 'IDEMPOTENCY_KEY_COLLISION'}

    return {
        'status': 'READY_TO_APPEND',
        'reason': 'APPROVAL_CONSUMPTION_READY',
        'previous_record_sha256': chain['tail_sha256'],
    }


def build_ledger_entry(
    req: ConsumptionRequest,
    *,
    previous_record_sha256: str | None = None,
) -> LedgerEntry:
    if previous_record_sha256 is not None and not DIGEST_RE.fullmatch(previous_record_sha256):
        raise ValueError('VALID_PREVIOUS_RECORD_SHA_REQUIRED')
    return LedgerEntry(
        workload_id=req.workload_id,
        candidate_sha=req.candidate_sha,
        receipt_sha256=req.receipt_sha256,
        receipt_nonce=req.receipt_nonce,
        action=req.action,
        idempotency_key=req.idempotency_key,
        consumed_at=req.consumed_at,
        source_reference=req.source_reference,
        previous_record_sha256=previous_record_sha256,
        record_sha256=record_digest(req, previous_record_sha256),
    )


def build_consumption_package(
    req: ConsumptionRequest,
    *,
    existing_entries: tuple[LedgerEntry, ...],
    now: datetime,
) -> dict:
    decision = validate_consumption(req, existing_entries=existing_entries, now=now)
    previous = decision.get('previous_record_sha256') if decision['status'] == 'READY_TO_APPEND' else None
    return {
        'schema': 'lom.approval-consumption-package/2',
        'status': decision['status'],
        'reason': decision['reason'],
        'record': _entry_payload(req, previous) if decision['status'] == 'READY_TO_APPEND' else None,
        'record_sha256': record_digest(req, previous) if decision['status'] == 'READY_TO_APPEND' else None,
        'previous_record_sha256': previous,
        'append_only_ledger_required': True,
        'tamper_evident_hash_chain_required': True,
        'single_use_receipt_required': True,
        'idempotent_retry_behavior': 'IDEMPOTENT_NOOP',
        'auto_merge': 'DISABLED',
        'production_execution': 'DISABLED',
        'external_action_execution': 'DISABLED',
    }
