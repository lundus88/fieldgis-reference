import unittest
from datetime import datetime, timezone, timedelta
from collector import SourceEvidence, normalize, missing_source

NOW = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
SHA = 'a' * 40


def ev(**overrides):
    data = dict(
        workload_id='ebkl', evidence_sha=SHA, measured_at='2026-09-14T23:00:00Z',
        sample_count=10, success_rate=.99, correctness=.98, safety=.999,
        p95_latency_ms=1200, source_kind='ci_artifact', source_reference='run:1',
        production_sensitive=False,
    )
    data.update(overrides)
    return SourceEvidence(**data)


class CollectorTests(unittest.TestCase):
    def test_ready(self):
        self.assertEqual(normalize(ev(), SHA, NOW)['health'], 'MONITOR')

    def test_production_source_forbidden(self):
        self.assertEqual(normalize(ev(production_sensitive=True), SHA, NOW)['reason'], 'PRODUCTION_SENSITIVE_SOURCE_FORBIDDEN')

    def test_bad_source_kind_holds(self):
        self.assertEqual(normalize(ev(source_kind='production_runtime'), SHA, NOW)['reason'], 'SOURCE_KIND_NOT_ALLOWED')

    def test_reference_required(self):
        self.assertEqual(normalize(ev(source_reference=''), SHA, NOW)['reason'], 'SOURCE_REFERENCE_REQUIRED')

    def test_sha_mismatch_holds(self):
        self.assertEqual(normalize(ev(), 'b' * 40, NOW)['reason'], 'EVIDENCE_SHA_MISMATCH')

    def test_sample_required(self):
        self.assertEqual(normalize(ev(sample_count=0), SHA, NOW)['reason'], 'SAMPLE_COUNT_REQUIRED')

    def test_invalid_success_holds(self):
        self.assertEqual(normalize(ev(success_rate=1.1), SHA, NOW)['reason'], 'INVALID_RATE')

    def test_invalid_correctness_holds(self):
        self.assertEqual(normalize(ev(correctness=-.1), SHA, NOW)['reason'], 'INVALID_RATE')

    def test_invalid_safety_holds(self):
        self.assertEqual(normalize(ev(safety=1.1), SHA, NOW)['reason'], 'INVALID_RATE')

    def test_invalid_latency_holds(self):
        self.assertEqual(normalize(ev(p95_latency_ms=-1), SHA, NOW)['reason'], 'INVALID_LATENCY')

    def test_bad_time_holds(self):
        self.assertEqual(normalize(ev(measured_at='bad'), SHA, NOW)['reason'], 'INVALID_MEASUREMENT_TIME')

    def test_stale_holds(self):
        old = (NOW - timedelta(hours=49)).isoformat().replace('+00:00', 'Z')
        self.assertEqual(normalize(ev(measured_at=old), SHA, NOW)['reason'], 'STALE_OR_FUTURE_EVIDENCE')

    def test_future_holds(self):
        future = (NOW + timedelta(minutes=1)).isoformat().replace('+00:00', 'Z')
        self.assertEqual(normalize(ev(measured_at=future), SHA, NOW)['reason'], 'STALE_OR_FUTURE_EVIDENCE')

    def test_safety_escalates(self):
        self.assertEqual(normalize(ev(safety=.95), SHA, NOW)['health'], 'HUMAN_REVIEW')

    def test_performance_auto_prepare(self):
        self.assertEqual(normalize(ev(success_rate=.90), SHA, NOW)['health'], 'AUTO_PREPARE')

    def test_missing_source_holds(self):
        self.assertEqual(missing_source('sabahlot')['status'], 'HOLD')


if __name__ == '__main__':
    unittest.main()
