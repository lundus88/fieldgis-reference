import unittest
from datetime import datetime, timedelta, timezone

from receipt import ApprovalReceipt, build_receipt_package, receipt_digest, validate_receipt

NOW = datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc)
CAND = 'b' * 40
PKG = 'c' * 64


def req(**overrides):
    data = dict(
        workload_id='ebkl',
        candidate_sha=CAND,
        decision_package_sha256=PKG,
        actor_id='human:director',
        decision='APPROVE',
        nonce='approval-nonce-0001',
        issued_at=(NOW - timedelta(minutes=5)).isoformat(),
        expires_at=(NOW + timedelta(minutes=25)).isoformat(),
        source_reference='human://approval/pr/243',
    )
    data.update(overrides)
    return ApprovalReceipt(**data)


class ApprovalReceiptTests(unittest.TestCase):
    def validate(self, receipt=None, **kwargs):
        return validate_receipt(
            receipt or req(),
            expected_candidate_sha=kwargs.pop('expected_candidate_sha', CAND),
            expected_decision_package_sha256=kwargs.pop('expected_decision_package_sha256', PKG),
            now=kwargs.pop('now', NOW),
            consumed_nonces=kwargs.pop('consumed_nonces', frozenset()),
        )

    def test_valid_approval(self):
        self.assertEqual(self.validate()['status'], 'APPROVED_FOR_BOUND_ACTION')

    def test_candidate_mismatch_holds(self):
        self.assertEqual(self.validate(expected_candidate_sha='d' * 40)['reason'], 'CANDIDATE_SHA_MISMATCH')

    def test_package_digest_mismatch_holds(self):
        self.assertEqual(self.validate(expected_decision_package_sha256='e' * 64)['reason'], 'DECISION_PACKAGE_DIGEST_MISMATCH')

    def test_malformed_candidate_holds(self):
        self.assertEqual(self.validate(req(candidate_sha='bad'))['reason'], 'EXACT_CANDIDATE_SHA_REQUIRED')

    def test_malformed_package_digest_holds(self):
        self.assertEqual(self.validate(req(decision_package_sha256='bad'))['reason'], 'DECISION_PACKAGE_DIGEST_REQUIRED')

    def test_missing_actor_holds(self):
        self.assertEqual(self.validate(req(actor_id=''))['reason'], 'ACTOR_ID_REQUIRED')

    def test_unknown_decision_holds(self):
        self.assertEqual(self.validate(req(decision='MAYBE'))['reason'], 'UNKNOWN_DECISION')

    def test_bad_nonce_holds(self):
        self.assertEqual(self.validate(req(nonce='short'))['reason'], 'VALID_NONCE_REQUIRED')

    def test_consumed_nonce_holds(self):
        self.assertEqual(self.validate(consumed_nonces={'approval-nonce-0001'})['reason'], 'NONCE_ALREADY_CONSUMED')

    def test_missing_source_holds(self):
        self.assertEqual(self.validate(req(source_reference=''))['reason'], 'SOURCE_REFERENCE_REQUIRED')

    def test_future_issued_at_holds(self):
        future = (NOW + timedelta(minutes=1)).isoformat()
        self.assertEqual(self.validate(req(issued_at=future))['reason'], 'ISSUED_AT_IN_FUTURE')

    def test_invalid_expiry_window_holds(self):
        old = (NOW - timedelta(minutes=10)).isoformat()
        self.assertEqual(self.validate(req(expires_at=old))['reason'], 'INVALID_EXPIRY_WINDOW')

    def test_expired_receipt_holds(self):
        expiry = (NOW - timedelta(minutes=1)).isoformat()
        issued = (NOW - timedelta(minutes=10)).isoformat()
        self.assertEqual(self.validate(req(issued_at=issued, expires_at=expiry))['reason'], 'APPROVAL_RECEIPT_EXPIRED')

    def test_reject_is_preserved(self):
        self.assertEqual(self.validate(req(decision='REJECT'))['status'], 'REJECTED')

    def test_request_changes_is_preserved(self):
        self.assertEqual(self.validate(req(decision='REQUEST_CHANGES'))['status'], 'REQUEST_CHANGES')

    def test_digest_is_deterministic(self):
        self.assertEqual(receipt_digest(req()), receipt_digest(req()))

    def test_digest_changes_with_nonce(self):
        self.assertNotEqual(receipt_digest(req()), receipt_digest(req(nonce='approval-nonce-0002')))

    def test_package_preserves_authority_boundaries(self):
        package = build_receipt_package(req())
        self.assertTrue(package['single_use_nonce_required'])
        self.assertTrue(package['bound_to_exact_candidate'])
        self.assertTrue(package['bound_to_exact_decision_package'])
        self.assertEqual(package['auto_approval'], 'DISABLED')
        self.assertEqual(package['auto_merge'], 'DISABLED')
        self.assertEqual(package['production_execution'], 'DISABLED')


if __name__ == '__main__':
    unittest.main()
