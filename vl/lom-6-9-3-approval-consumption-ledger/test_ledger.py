import unittest
from dataclasses import replace
from datetime import datetime, timezone

from ledger import (
    ConsumptionRequest,
    LedgerEntry,
    build_consumption_package,
    build_ledger_entry,
    record_digest,
    validate_consumption,
    verify_ledger_chain,
)

NOW = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)


def req(**kw):
    data = dict(
        workload_id='ebkl',
        candidate_sha='b' * 40,
        receipt_sha256='c' * 64,
        receipt_nonce='approval-nonce-0001',
        receipt_status='APPROVED_FOR_BOUND_ACTION',
        action='PROTECTED_MAIN_MERGE',
        idempotency_key='consume-ebkl-0001',
        consumed_at='2026-09-14T23:59:00Z',
        source_reference='approval://receipt/1',
    )
    data.update(kw)
    return ConsumptionRequest(**data)


class LedgerTests(unittest.TestCase):
    def test_ready(self):
        self.assertEqual(validate_consumption(req(), now=NOW)['status'], 'READY_TO_APPEND')

    def test_missing_workload_holds(self):
        self.assertEqual(validate_consumption(req(workload_id=''), now=NOW)['status'], 'HOLD')

    def test_bad_candidate_holds(self):
        self.assertEqual(validate_consumption(req(candidate_sha='x'), now=NOW)['reason'], 'EXACT_CANDIDATE_SHA_REQUIRED')

    def test_bad_receipt_digest_holds(self):
        self.assertEqual(validate_consumption(req(receipt_sha256='x'), now=NOW)['reason'], 'RECEIPT_DIGEST_REQUIRED')

    def test_bad_nonce_holds(self):
        self.assertEqual(validate_consumption(req(receipt_nonce='short'), now=NOW)['reason'], 'VALID_RECEIPT_NONCE_REQUIRED')

    def test_non_approved_receipt_holds(self):
        self.assertEqual(validate_consumption(req(receipt_status='REJECTED'), now=NOW)['reason'], 'APPROVED_RECEIPT_REQUIRED')

    def test_missing_action_holds(self):
        self.assertEqual(validate_consumption(req(action=''), now=NOW)['reason'], 'ACTION_REQUIRED')

    def test_bad_idempotency_holds(self):
        self.assertEqual(validate_consumption(req(idempotency_key='short'), now=NOW)['reason'], 'VALID_IDEMPOTENCY_KEY_REQUIRED')

    def test_missing_source_holds(self):
        self.assertEqual(validate_consumption(req(source_reference=''), now=NOW)['reason'], 'SOURCE_REFERENCE_REQUIRED')

    def test_bad_time_holds(self):
        self.assertEqual(validate_consumption(req(consumed_at='bad'), now=NOW)['reason'], 'VALID_CONSUMED_AT_REQUIRED')

    def test_future_time_holds(self):
        self.assertEqual(validate_consumption(req(consumed_at='2026-09-15T00:01:00Z'), now=NOW)['reason'], 'CONSUMED_AT_IN_FUTURE')

    def test_same_retry_is_noop(self):
        r = req()
        entry = build_ledger_entry(r)
        self.assertEqual(validate_consumption(r, existing_entries=(entry,), now=NOW)['status'], 'IDEMPOTENT_NOOP')

    def test_receipt_rebind_holds(self):
        entry = build_ledger_entry(req())
        result = validate_consumption(req(action='PRODUCTION_RELEASE'), existing_entries=(entry,), now=NOW)
        self.assertEqual(result['reason'], 'RECEIPT_REPLAY_OR_REBIND_ATTEMPT')

    def test_nonce_rebind_holds(self):
        entry = build_ledger_entry(req())
        result = validate_consumption(req(receipt_sha256='d' * 64), existing_entries=(entry,), now=NOW)
        self.assertEqual(result['reason'], 'RECEIPT_REPLAY_OR_REBIND_ATTEMPT')

    def test_idempotency_collision_holds(self):
        entry = build_ledger_entry(req(receipt_sha256='d' * 64, receipt_nonce='approval-nonce-0002'))
        result = validate_consumption(req(), existing_entries=(entry,), now=NOW)
        self.assertEqual(result['reason'], 'IDEMPOTENCY_KEY_COLLISION')

    def test_invalid_existing_digest_format_holds(self):
        entry = replace(build_ledger_entry(req()), record_sha256='bad')
        self.assertEqual(validate_consumption(req(receipt_nonce='approval-nonce-0002'), existing_entries=(entry,), now=NOW)['reason'], 'INVALID_EXISTING_LEDGER_ENTRY')

    def test_valid_looking_but_wrong_digest_holds(self):
        entry = replace(build_ledger_entry(req()), record_sha256='f' * 64)
        result = validate_consumption(req(receipt_sha256='d' * 64, receipt_nonce='approval-nonce-0002', idempotency_key='consume-ebkl-0002'), existing_entries=(entry,), now=NOW)
        self.assertEqual(result['reason'], 'LEDGER_RECORD_DIGEST_MISMATCH')

    def test_two_record_chain_is_valid(self):
        first = build_ledger_entry(req())
        second_req = req(receipt_sha256='d' * 64, receipt_nonce='approval-nonce-0002', idempotency_key='consume-ebkl-0002')
        second = build_ledger_entry(second_req, previous_record_sha256=first.record_sha256)
        result = verify_ledger_chain((first, second))
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(result['tail_sha256'], second.record_sha256)

    def test_chain_break_holds(self):
        first = build_ledger_entry(req())
        second_req = req(receipt_sha256='d' * 64, receipt_nonce='approval-nonce-0002', idempotency_key='consume-ebkl-0002')
        second = build_ledger_entry(second_req, previous_record_sha256='e' * 64)
        self.assertEqual(verify_ledger_chain((first, second))['reason'], 'LEDGER_CHAIN_BROKEN')

    def test_reordered_chain_holds(self):
        first = build_ledger_entry(req())
        second_req = req(receipt_sha256='d' * 64, receipt_nonce='approval-nonce-0002', idempotency_key='consume-ebkl-0002')
        second = build_ledger_entry(second_req, previous_record_sha256=first.record_sha256)
        self.assertEqual(verify_ledger_chain((second, first))['reason'], 'LEDGER_CHAIN_BROKEN')

    def test_mutated_content_with_old_digest_holds(self):
        first = build_ledger_entry(req())
        tampered = replace(first, action='PRODUCTION_RELEASE')
        self.assertEqual(verify_ledger_chain((tampered,))['reason'], 'LEDGER_RECORD_DIGEST_MISMATCH')

    def test_record_digest_deterministic(self):
        self.assertEqual(record_digest(req()), record_digest(req()))

    def test_package_chains_to_existing_tail(self):
        first = build_ledger_entry(req())
        next_req = req(receipt_sha256='d' * 64, receipt_nonce='approval-nonce-0002', idempotency_key='consume-ebkl-0002')
        p = build_consumption_package(next_req, existing_entries=(first,), now=NOW)
        self.assertEqual(p['status'], 'READY_TO_APPEND')
        self.assertEqual(p['previous_record_sha256'], first.record_sha256)
        self.assertTrue(p['tamper_evident_hash_chain_required'])

    def test_package_preserves_execution_boundaries(self):
        p = build_consumption_package(req(), existing_entries=(), now=NOW)
        self.assertEqual(p['status'], 'READY_TO_APPEND')
        self.assertEqual(len(p['record_sha256']), 64)
        self.assertEqual(p['auto_merge'], 'DISABLED')
        self.assertEqual(p['production_execution'], 'DISABLED')
        self.assertEqual(p['external_action_execution'], 'DISABLED')


if __name__ == '__main__':
    unittest.main()
