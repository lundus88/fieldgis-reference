import unittest
from datetime import datetime, timezone, timedelta
from dataclasses import replace

from artifact_v2 import (
    build_from_semantics,
    derived_metrics_digest,
    producer_contract_v2,
    validate_artifact_v2,
)

NOW = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
MEASURED = '2026-09-14T23:30:00Z'
SHA = 'a' * 40


def semantics_result(**overrides):
    metrics = {
        'workload_id': 'ebkl',
        'evidence_sha': SHA,
        'sample_count': 100,
        'success_rate': 1.0,
        'correctness': 1.0,
        'safety': 1.0,
        'critical_safety_failures': 0,
        'p95_latency_ms': 120,
        'source_reference': 'ci://ebkl/run/1',
        'derivation': 'DETERMINISTIC_FROM_RAW_COUNTERS',
    }
    metrics.update(overrides)
    return {'status': 'READY', 'health': 'MONITOR', 'reason': 'DERIVED_METRICS_READY', 'metrics': metrics}


def validate(artifact, metrics=None, **kwargs):
    if metrics is None:
        metrics = semantics_result()['metrics']
    return validate_artifact_v2(
        artifact,
        expected_workload_id=kwargs.pop('expected_workload_id', 'ebkl'),
        expected_sha=kwargs.pop('expected_sha', SHA),
        expected_derived_metrics=metrics,
        now=kwargs.pop('now', NOW),
        **kwargs,
    )


class CriticalSafetyArtifactTests(unittest.TestCase):
    def test_build_from_ready_semantics(self):
        artifact = build_from_semantics(semantics_result=semantics_result(), measured_at=MEASURED)
        self.assertEqual(artifact.schema, 'lom.technical-metrics-artifact/2')
        self.assertEqual(artifact.critical_safety_failures, 0)

    def test_non_ready_semantics_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SEMANTICS_READY_REQUIRED'):
            build_from_semantics(semantics_result={'status': 'HOLD'}, measured_at=MEASURED)

    def test_missing_critical_field_rejected(self):
        result = semantics_result()
        del result['metrics']['critical_safety_failures']
        with self.assertRaisesRegex(ValueError, 'COMPLETE_DERIVED_METRICS_REQUIRED'):
            build_from_semantics(semantics_result=result, measured_at=MEASURED)

    def test_digest_is_deterministic(self):
        metrics = semantics_result()['metrics']
        self.assertEqual(derived_metrics_digest(metrics), derived_metrics_digest(metrics))

    def test_valid_artifact_monitors(self):
        result = semantics_result()
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        self.assertEqual(validate(artifact, result['metrics'])['health'], 'MONITOR')

    def test_critical_failure_forces_human_review_even_with_perfect_safety_rate(self):
        result = semantics_result(critical_safety_failures=1, safety=1.0)
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        decision = validate(artifact, result['metrics'])
        self.assertEqual(decision['health'], 'HUMAN_REVIEW')
        self.assertEqual(decision['reason'], 'CRITICAL_SAFETY_FAILURE')

    def test_safety_threshold_still_human_review(self):
        result = semantics_result(safety=0.98)
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        self.assertEqual(validate(artifact, result['metrics'])['reason'], 'SAFETY_THRESHOLD_BREACH')

    def test_performance_degradation_auto_prepare(self):
        result = semantics_result(success_rate=0.94)
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        self.assertEqual(validate(artifact, result['metrics'])['health'], 'AUTO_PREPARE')

    def test_digest_tamper_holds(self):
        result = semantics_result()
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        artifact = replace(artifact, derived_metrics_sha256='b' * 64)
        self.assertEqual(validate(artifact, result['metrics'])['reason'], 'DERIVED_METRICS_DIGEST_MISMATCH')

    def test_critical_count_tamper_holds(self):
        result = semantics_result(critical_safety_failures=1)
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        artifact = replace(artifact, critical_safety_failures=0)
        self.assertEqual(validate(artifact, result['metrics'])['reason'], 'DERIVED_METRICS_BINDING_MISMATCH')

    def test_workload_mismatch_holds(self):
        result = semantics_result()
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        self.assertEqual(validate(artifact, result['metrics'], expected_workload_id='sabahlot')['reason'], 'WORKLOAD_MISMATCH')

    def test_evidence_sha_mismatch_holds(self):
        result = semantics_result()
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        self.assertEqual(validate(artifact, result['metrics'], expected_sha='b' * 40)['reason'], 'EVIDENCE_SHA_MISMATCH')

    def test_negative_critical_count_holds(self):
        result = semantics_result(critical_safety_failures=-1)
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        self.assertEqual(validate(artifact, result['metrics'])['reason'], 'INVALID_CRITICAL_SAFETY_COUNT')

    def test_stale_artifact_holds(self):
        result = semantics_result()
        artifact = build_from_semantics(semantics_result=result, measured_at='2026-09-10T00:00:00Z')
        self.assertEqual(validate(artifact, result['metrics'])['reason'], 'STALE_OR_FUTURE_ARTIFACT')

    def test_future_artifact_holds(self):
        result = semantics_result()
        artifact = build_from_semantics(semantics_result=result, measured_at='2026-09-16T00:00:00Z')
        self.assertEqual(validate(artifact, result['metrics'])['reason'], 'STALE_OR_FUTURE_ARTIFACT')

    def test_producer_contract_forbids_defaults(self):
        contract = producer_contract_v2()
        self.assertEqual(contract['manual_metric_defaults'], 'FORBIDDEN')
        self.assertEqual(contract['missing_critical_safety_policy'], 'HOLD')

    def test_producer_contract_disables_production(self):
        contract = producer_contract_v2()
        self.assertEqual(contract['production_action'], 'DISABLED')
        self.assertEqual(contract['cross_repo_write'], 'DISABLED')

    def test_output_marks_critical_propagated(self):
        result = semantics_result()
        artifact = build_from_semantics(semantics_result=result, measured_at=MEASURED)
        self.assertTrue(validate(artifact, result['metrics'])['critical_safety_propagated'])


if __name__ == '__main__':
    unittest.main()
