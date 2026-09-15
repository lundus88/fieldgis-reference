import unittest
from datetime import datetime, timedelta, timezone

from receipt import ApprovalReceipt, build_receipt_package, receipt_digest, sign_receipt, validate_receipt

NOW = datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc)
CAND = 'b' * 40
PKG = 'c' * 64
ISSUER_KEY = b'test-only-issuer-key-not-production'
TRUSTED_ISSUERS = {'github-oidc:test': ISSUER_KEY}
TRUSTED_ACTORS = {'human:director': 'github:user:215026954'}


def unsigned_req(**overrides):
    data = dict(
        workload_id='ebkl',
        candidate_sha=CAND,
        decision_package_sha256=PKG,
        actor_id='human:director',
        identity_subject='github:user:215026954',
        issuer_id='github-oidc:test',
        decision='APPROVE',
        nonce='approval-nonce-0001',
        issued_at=(NOW - timedelta(minutes=5)).isoformat(),
        expires_at=(NOW + timedelta(minutes=25)).isoformat(),
        source_reference='human://approval/pr/243',
    )
    data.update(overrides)
    return ApprovalReceipt(**data)


def req(**overrides):
    return sign_receipt(unsigned_req(**overrides), issuer_key=ISSUER_KEY)


class ApprovalReceiptTests(unittest.TestCase):
    def validate(self, receipt=None, **kwargs):
        return validate_receipt(
            receipt or req(),
            expected_candidate_sha=kwargs.pop('expected_candidate_sha', CAND),
            expected_decision_package_sha256=kwargs.pop('expected_decision_package_sha256', PKG),
            now=kwargs.pop('now', NOW),
            trusted_issuer_keys=kwargs.pop('trusted_issuer_keys', TRUSTED_ISSUERS),
            trusted_actor_subjects=kwargs.pop('trusted_actor_subjects', TRUSTED_ACTORS),
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

    def test_missing_identity_subject_holds(self):
        self.assertEqual(self.validate(req(identity_subject=''))['reason'], 'IDENTITY_SUBJECT_REQUIRED')

    def test_unknown_actor_holds(self):
        r = req(actor_id='human:unknown')
        self.assertEqual(self.validate(r)['reason'], 'UNTRUSTED_HUMAN_ACTOR')

    def test_identity_binding_mismatch_holds(self):
        r = req(identity_subject='github:user:999')
        self.assertEqual(self.validate(r)['reason'], 'HUMAN_IDENTITY_BINDING_MISMATCH')

    def test_unknown_issuer_holds(self):
        r = sign_receipt(unsigned_req(issuer_id='unknown-issuer'), issuer_key=ISSUER_KEY)
        self.assertEqual(self.validate(r)['reason'], 'UNTRUSTED_IDENTITY_ISSUER')

    def test_missing_signature_holds(self):
        self.assertEqual(self.validate(unsigned_req())['reason'], 'SIGNATURE_REQUIRED')

    def test_tampered_signed_receipt_holds(self):
        signed = req()
        tampered = ApprovalReceipt(**{**signed.__dict__, 'decision': 'REJECT'})
        self.assertEqual(self.validate(tampered)['reason'], 'SIGNATURE_INVALID')

    def test_wrong_issuer_key_holds(self):
        signed = req()
        self.assertEqual(
            self.validate(signed, trusted_issuer_keys={'github-oidc:test': b'wrong-key'})['reason'],
            'SIGNATURE_INVALID',
        )

    def test_unknown_decision_holds_after_valid_signature(self):
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
        self.assertTrue(package['cryptographic_signature_required'])
        self.assertTrue(package['trusted_issuer_required'])
        self.assertTrue(package['trusted_human_identity_binding_required'])
        self.assertTrue(package['single_use_nonce_required'])
        self.assertTrue(package['bound_to_exact_candidate'])
        self.assertTrue(package['bound_to_exact_decision_package'])
        self.assertEqual(package['auto_approval'], 'DISABLED')
        self.assertEqual(package['auto_merge'], 'DISABLED')
        self.assertEqual(package['production_execution'], 'DISABLED')


if __name__ == '__main__':
    unittest.main()
