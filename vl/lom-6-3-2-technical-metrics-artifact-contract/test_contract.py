import unittest
from datetime import datetime, timedelta, timezone

from contract import MetricsArtifact, validate_artifact, build_template, producer_contract

NOW = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
SHA = 'a' * 40


def artifact(**overrides):
    data = dict(
        workload_id='ebkl',
        evidence_sha=SHA,
        measured_at=(NOW - timedelta(hours=1)).isoformat(),
        sample_count=10,
        success_rate=.99,
        correctness=.99,
        safety=.999,
        p95_latency_ms=900,
        source_reference='artifact:run:1',
    )
    data.update(overrides)
    return MetricsArtifact(**data)


class ContractTests(unittest.TestCase):
    def test_ready_monitor(self):
        r = validate_artifact(artifact(), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)
        self.assertEqual((r['status'], r['health']), ('READY', 'MONITOR'))

    def test_schema_mismatch_holds(self):
        self.assertEqual(validate_artifact(artifact(schema='x'), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'SCHEMA_MISMATCH')

    def test_workload_mismatch_holds(self):
        self.assertEqual(validate_artifact(artifact(workload_id='sabahlot'), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'WORKLOAD_MISMATCH')

    def test_invalid_sha_holds(self):
        self.assertEqual(validate_artifact(artifact(evidence_sha='bad'), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'INVALID_EVIDENCE_SHA')

    def test_sha_mismatch_holds(self):
        self.assertEqual(validate_artifact(artifact(evidence_sha='b'*40), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'EVIDENCE_SHA_MISMATCH')

    def test_missing_provenance_holds(self):
        self.assertEqual(validate_artifact(artifact(source_reference=''), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'PROVENANCE_REQUIRED')

    def test_wrong_source_kind_holds(self):
        self.assertEqual(validate_artifact(artifact(source_kind='manual'), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'PROVENANCE_REQUIRED')

    def test_sample_required(self):
        self.assertEqual(validate_artifact(artifact(sample_count=0), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'SAMPLE_COUNT_REQUIRED')

    def test_invalid_rate_holds(self):
        self.assertEqual(validate_artifact(artifact(success_rate=1.1), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'INVALID_RATE')

    def test_invalid_latency_holds(self):
        self.assertEqual(validate_artifact(artifact(p95_latency_ms=-1), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'INVALID_LATENCY')

    def test_invalid_time_holds(self):
        self.assertEqual(validate_artifact(artifact(measured_at='bad'), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'INVALID_MEASUREMENT_TIME')

    def test_stale_holds(self):
        t = (NOW - timedelta(hours=49)).isoformat()
        self.assertEqual(validate_artifact(artifact(measured_at=t), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'STALE_OR_FUTURE_ARTIFACT')

    def test_future_holds(self):
        t = (NOW + timedelta(minutes=1)).isoformat()
        self.assertEqual(validate_artifact(artifact(measured_at=t), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)['reason'], 'STALE_OR_FUTURE_ARTIFACT')

    def test_safety_breach_human_review(self):
        r = validate_artifact(artifact(safety=.98), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)
        self.assertEqual(r['health'], 'HUMAN_REVIEW')

    def test_performance_auto_prepare(self):
        r = validate_artifact(artifact(success_rate=.90), expected_workload_id='ebkl', expected_sha=SHA, now=NOW)
        self.assertEqual(r['health'], 'AUTO_PREPARE')

    def test_template_requires_derived_metrics_and_contract_is_safe(self):
        with self.assertRaisesRegex(ValueError, 'DERIVED_METRICS_REQUIRED'):
            build_template(workload_id='ebkl', evidence_sha=SHA, measured_at=NOW.isoformat(), source_reference='run:1')
        t = build_template(
            workload_id='ebkl', evidence_sha=SHA, measured_at=NOW.isoformat(), source_reference='run:1',
            sample_count=10, success_rate=.9, correctness=.95, safety=1.0, p95_latency_ms=100,
        )
        p = producer_contract()
        self.assertEqual(t['success_rate'], .9)
        self.assertEqual(p['metric_values'], 'DERIVED_REQUIRED')
        self.assertEqual(p['permissions'], {'contents': 'read'})
        self.assertEqual(p['production_credentials'], 'FORBIDDEN')
        self.assertEqual(p['fabricated_metrics'], 'FORBIDDEN')
        self.assertEqual(p['cross_repo_write'], 'DISABLED')


if __name__ == '__main__':
    unittest.main()
