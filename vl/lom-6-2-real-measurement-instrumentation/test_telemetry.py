import unittest
from datetime import datetime, timedelta, timezone

from telemetry import WorkloadAnchor, TechnicalMeasurement, validate_measurement, aggregate, health

NOW = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
ANCHOR = WorkloadAnchor('ebkl', 'a' * 40)


def m(**overrides):
    data = dict(
        workload_id='ebkl',
        evidence_sha='a' * 40,
        measured_at=NOW - timedelta(hours=1),
        sample_count=10,
        success_rate=.98,
        correctness=.97,
        safety=.999,
        p95_latency_ms=1200,
        source_kind='ci_artifact',
        source_reference='run:1',
    )
    data.update(overrides)
    return TechnicalMeasurement(**data)


class TelemetryTests(unittest.TestCase):
    def test_valid_measurement_ready(self):
        self.assertEqual(validate_measurement(m(), ANCHOR, now=NOW)['status'], 'READY')

    def test_workload_mismatch_holds(self):
        self.assertEqual(validate_measurement(m(workload_id='sabahlot'), ANCHOR, now=NOW)['reason'], 'WORKLOAD_MISMATCH')

    def test_sha_mismatch_holds(self):
        self.assertEqual(validate_measurement(m(evidence_sha='b' * 40), ANCHOR, now=NOW)['reason'], 'EVIDENCE_SHA_MISMATCH')

    def test_sample_required(self):
        self.assertEqual(validate_measurement(m(sample_count=0), ANCHOR, now=NOW)['reason'], 'SAMPLE_REQUIRED')

    def test_provenance_required(self):
        self.assertEqual(validate_measurement(m(source_kind='unknown'), ANCHOR, now=NOW)['reason'], 'PROVENANCE_REQUIRED')

    def test_invalid_rate_holds(self):
        self.assertEqual(validate_measurement(m(success_rate=1.1), ANCHOR, now=NOW)['reason'], 'INVALID_RATE')

    def test_invalid_latency_holds(self):
        self.assertEqual(validate_measurement(m(p95_latency_ms=-1), ANCHOR, now=NOW)['reason'], 'INVALID_LATENCY')

    def test_stale_holds(self):
        self.assertEqual(validate_measurement(m(measured_at=NOW - timedelta(hours=25)), ANCHOR, now=NOW)['reason'], 'STALE_OR_FUTURE_MEASUREMENT')

    def test_future_holds(self):
        self.assertEqual(validate_measurement(m(measured_at=NOW + timedelta(minutes=1)), ANCHOR, now=NOW)['reason'], 'STALE_OR_FUTURE_MEASUREMENT')

    def test_safety_breach_human_review(self):
        self.assertEqual(validate_measurement(m(safety=.95), ANCHOR, now=NOW)['status'], 'HUMAN_REVIEW')

    def test_aggregate_weighted(self):
        result = aggregate([
            m(sample_count=10, success_rate=.9, correctness=.8, source_reference='a'),
            m(sample_count=30, success_rate=1.0, correctness=1.0, source_reference='b'),
        ], ANCHOR, now=NOW)
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(result['sample_count'], 40)
        self.assertAlmostEqual(result['success_rate'], .975)
        self.assertAlmostEqual(result['correctness'], .95)

    def test_aggregate_uses_conservative_latency(self):
        result = aggregate([m(p95_latency_ms=1000), m(p95_latency_ms=2200, source_reference='b')], ANCHOR, now=NOW)
        self.assertEqual(result['p95_latency_ms'], 2200)

    def test_aggregate_no_valid_holds(self):
        result = aggregate([m(evidence_sha='b' * 40)], ANCHOR, now=NOW)
        self.assertEqual(result['status'], 'HOLD')

    def test_mixed_valid_and_unsafe_escalates_human_review(self):
        result = aggregate([
            m(source_reference='safe'),
            m(safety=.95, source_reference='unsafe'),
        ], ANCHOR, now=NOW)
        self.assertEqual(result['status'], 'HUMAN_REVIEW')
        self.assertEqual(result['reason'], 'BATCH_CONTAINS_SAFETY_REVIEW_MEASUREMENT')

    def test_mixed_valid_and_sha_mismatch_holds(self):
        result = aggregate([
            m(source_reference='safe'),
            m(evidence_sha='b' * 40, source_reference='bad-sha'),
        ], ANCHOR, now=NOW)
        self.assertEqual(result['status'], 'HOLD')
        self.assertEqual(result['reason'], 'BATCH_CONTAINS_REJECTED_MEASUREMENT')

    def test_mixed_valid_and_stale_holds(self):
        result = aggregate([
            m(source_reference='safe'),
            m(measured_at=NOW - timedelta(hours=25), source_reference='stale'),
        ], ANCHOR, now=NOW)
        self.assertEqual(result['status'], 'HOLD')
        self.assertEqual(result['reason'], 'BATCH_CONTAINS_REJECTED_MEASUREMENT')

    def test_hold_precedes_human_review_in_mixed_rejections(self):
        result = aggregate([
            m(source_reference='safe'),
            m(safety=.95, source_reference='unsafe'),
            m(evidence_sha='b' * 40, source_reference='bad-sha'),
        ], ANCHOR, now=NOW)
        self.assertEqual(result['status'], 'HOLD')

    def test_health_monitor(self):
        self.assertEqual(health(aggregate([m()], ANCHOR, now=NOW))['health'], 'MONITOR')

    def test_health_auto_prepare(self):
        summary = aggregate([m(success_rate=.80, correctness=.85)], ANCHOR, now=NOW)
        self.assertEqual(health(summary)['health'], 'AUTO_PREPARE')

    def test_health_preserves_human_review(self):
        summary = aggregate([m(), m(safety=.95, source_reference='unsafe')], ANCHOR, now=NOW)
        self.assertEqual(health(summary)['health'], 'HUMAN_REVIEW')

    def test_health_hold_when_summary_not_ready(self):
        self.assertEqual(health({'status': 'HOLD', 'reason': 'X'})['health'], 'HOLD')


if __name__ == '__main__':
    unittest.main()
