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
    record_sha256: str


def _parse_time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _entry_payload(req: ConsumptionRequest) -> dict:
    return {
        'schema': 'lom.approval-consumption-ledger/1',
        'workload_id': req.workload_id,
        'candidate_sha': req.candidate_sha,
        'receipt_sha256': req.receipt_sha256,
        'receipt_nonce': req.receipt_nonce,
        'action': req.action,
        'idempotency_key': req.idempotency_key,
        'consumed_at': req.consumed_at,
        'source_reference': req.source_reference,
        'append_only': True,
        'single_use_receipt': True,
        'idempotent_retry_only': True,
        'production_execution': 'DISABLED',
    }


def record_digest(req: ConsumptionRequest) -> str:
    raw = json.dumps(_entry_payload(req), sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


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

    for entry in existing_entries:
        if not DIGEST_RE.fullmatch(entry.record_sha256 or ''):
            return {'status': 'HOLD', 'reason': 'INVALID_EXISTING_LEDGER_ENTRY'}
        if entry.receipt_sha256 == req.receipt_sha256 or entry.receipt_nonce == req.receipt_nonce:
            if _same_bound_operation(req, entry):
                return {'status': 'IDEMPOTENT_NOOP', 'reason': 'ALREADY_CONSUMED_SAME_BOUND_OPERATION'}
            return {'status': 'HOLD', 'reason': 'RECEIPT_REPLAY_OR_REBIND_ATTEMPT'}
        if entry.idempotency_key == req.idempotency_key:
            if _same_bound_operation(req, entry):
                return {'status': 'IDEMPOTENT_NOOP', 'reason': 'ALREADY_CONSUMED_SAME_BOUND_OPERATION'}
            return {'status': 'HOLD', 'reason': 'IDEMPOTENCY_KEY_COLLISION'}

    return {'status': 'READY_TO_APPEND', 'reason': 'APPROVAL_CONSUMPTION_READY'}


def build_ledger_entry(req: ConsumptionRequest) -> LedgerEntry:
    return LedgerEntry(
        workload_id=req.workload_id,
        candidate_sha=req.candidate_sha,
        receipt_sha256=req.receipt_sha256,
        receipt_nonce=req.receipt_nonce,
        action=req.action,
        idempotency_key=req.idempotency_key,
        consumed_at=req.consumed_at,
        source_reference=req.source_reference,
        record_sha256=record_digest(req),
    )


def build_consumption_package(req: ConsumptionRequest, *, existing_entries: tuple[LedgerEntry, ...], now: datetime) -> dict:
    decision = validate_consumption(req, existing_entries=existing_entries, now=now)
    return {
        'schema': 'lom.approval-consumption-package/1',
        'status': decision['status'],
        'reason': decision['reason'],
        'record': _entry_payload(req) if decision['status'] == 'READY_TO_APPEND' else None,
        'record_sha256': record_digest(req) if decision['status'] == 'READY_TO_APPEND' else None,
        'append_only_ledger_required': True,
        'single_use_receipt_required': True,
        'idempotent_retry_behavior': 'IDEMPOTENT_NOOP',
        'auto_merge': 'DISABLED',
        'production_execution': 'DISABLED',
        'external_action_execution': 'DISABLED',
    }
