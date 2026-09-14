import unittest

from replay import (
    DERIVATION_VERSION,
    ReplayClaim,
    build_claim,
    manifest,
    metrics_digest,
    raw_evidence_digest,
    replay,
    validate_claim,
)

SHA = 'a' * 40
RAW = {
    'workload_id': 'ebkl',
    'evidence_sha': SHA,
    'total_cases': 10,
    'successful_cases': 10,
    'correctness_checks': 10,
    'correctness_passed': 10,
    'safety_checks': 10,
    'safety_passed': 10,
    'critical_safety_failures': 0,
    'latency_samples_ms': [100, 120, 130],
    'source_reference': 'artifact:run:1',
}
METRICS = {
    'workload_id': 'ebkl',
    'evidence_sha': SHA,
    'sample_count': 10,
    'success_rate': 1.0,
    'correctness': 1.0,
    'safety': 1.0,
    'p95_latency_ms': 130,
    'source_reference': 'artifact:run:1',
    'derivation': 'DETERMINISTIC_FROM_RAW_COUNTERS',
    'critical_safety_failures': 0,
}


def claim(**overrides):
    c = build_claim(
        workload_id='ebkl',
        evidence_sha=SHA,
        raw=RAW,
        metrics=METRICS,
        source_reference='replay:run:1',
    )
    data = c.__dict__.copy()
    data.update(overrides)
    return ReplayClaim(**data)


class ReplayTests(unittest.TestCase):
    def test_ready_replay(self):
        r = replay(claim(), raw=RAW, replayed_metrics=METRICS, expected_workload_id='ebkl', expected_evidence_sha=SHA)
        self.assertEqual((r['status'], r['reason']), ('READY', 'REPLAY_REPRODUCIBLE'))

    def test_schema_mismatch_holds(self):
        self.assertEqual(validate_claim(claim(schema='x'), expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'REPLAY_SCHEMA_MISMATCH')

    def test_workload_mismatch_holds(self):
        self.assertEqual(validate_claim(claim(workload_id='sabahlot'), expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'WORKLOAD_MISMATCH')

    def test_evidence_sha_mismatch_holds(self):
        self.assertEqual(validate_claim(claim(evidence_sha='b'*40), expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'EVIDENCE_SHA_MISMATCH')

    def test_derivation_version_mismatch_holds(self):
        self.assertEqual(validate_claim(claim(derivation_version='v2'), expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'DERIVATION_VERSION_MISMATCH')

    def test_invalid_raw_digest_holds(self):
        self.assertEqual(validate_claim(claim(raw_evidence_sha256='bad'), expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'INVALID_RAW_EVIDENCE_DIGEST')

    def test_invalid_metrics_digest_holds(self):
        self.assertEqual(validate_claim(claim(expected_metrics_sha256='bad'), expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'INVALID_METRICS_DIGEST')

    def test_missing_provenance_holds(self):
        self.assertEqual(validate_claim(claim(source_reference=''), expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'PROVENANCE_REQUIRED')

    def test_raw_tampering_holds(self):
        tampered = dict(RAW)
        tampered['successful_cases'] = 9
        self.assertEqual(replay(claim(), raw=tampered, replayed_metrics=METRICS, expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'RAW_EVIDENCE_DIGEST_MISMATCH')

    def test_metrics_tampering_holds(self):
        tampered = dict(METRICS)
        tampered['success_rate'] = .9
        self.assertEqual(replay(claim(), raw=RAW, replayed_metrics=tampered, expected_workload_id='ebkl', expected_evidence_sha=SHA)['reason'], 'REPLAY_METRICS_MISMATCH')

    def test_digest_is_deterministic_for_key_order(self):
        reverse = dict(reversed(list(RAW.items())))
        self.assertEqual(raw_evidence_digest(RAW), raw_evidence_digest(reverse))

    def test_metrics_digest_is_deterministic_for_key_order(self):
        reverse = dict(reversed(list(METRICS.items())))
        self.assertEqual(metrics_digest(METRICS), metrics_digest(reverse))

    def test_changed_raw_changes_digest(self):
        changed = dict(RAW)
        changed['total_cases'] = 11
        self.assertNotEqual(raw_evidence_digest(RAW), raw_evidence_digest(changed))

    def test_changed_metrics_changes_digest(self):
        changed = dict(METRICS)
        changed['p95_latency_ms'] = 131
        self.assertNotEqual(metrics_digest(METRICS), metrics_digest(changed))

    def test_manifest_governance(self):
        m = manifest(claim())
        self.assertTrue(m['replay_required'])
        self.assertEqual(m['mismatch_policy'], 'HOLD')
        self.assertEqual(m['production_authority'], 'HUMAN_ONLY')

    def test_default_derivation_version_is_pinned(self):
        self.assertEqual(claim().derivation_version, DERIVATION_VERSION)


if __name__ == '__main__':
    unittest.main()
