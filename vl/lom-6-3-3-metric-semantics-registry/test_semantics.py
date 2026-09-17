import unittest

from semantics import RawMetricEvidence, derive_metrics, semantics_registry

SHA = 'a' * 40


def raw(**overrides):
    data = dict(
        workload_id='ebkl',
        evidence_sha=SHA,
        total_cases=20,
        successful_cases=19,
        correctness_checks=20,
        correctness_passed=20,
        safety_checks=100,
        safety_passed=100,
        critical_safety_failures=0,
        latency_samples_ms=(100, 120, 130, 140, 150, 160, 170, 180, 190, 200),
        source_reference='artifact:run:1',
    )
    data.update(overrides)
    return RawMetricEvidence(**data)


class SemanticsTests(unittest.TestCase):
    def test_derives_metrics(self):
        r = derive_metrics(raw())
        self.assertEqual(r['status'], 'READY')
        self.assertEqual(r['metrics']['success_rate'], .95)
        self.assertEqual(r['metrics']['correctness'], 1.0)
        self.assertEqual(r['metrics']['safety'], 1.0)
        self.assertEqual(r['metrics']['p95_latency_ms'], 200)

    def test_unregistered_workload_holds(self):
        self.assertEqual(derive_metrics(raw(workload_id='x'))['reason'], 'WORKLOAD_SEMANTICS_NOT_REGISTERED')

    def test_portfolio_workloads_are_registered(self):
        registry = semantics_registry()
        for workload in ('vl', 'ebkl', 'sabahlot', 'lunduslead', 'urusmy', 'kontenstudio'):
            self.assertIn(workload, registry)
        self.assertNotIn('slp', registry)

    def test_new_portfolio_workloads_use_same_deterministic_derivation(self):
        for workload in ('vl', 'urusmy', 'kontenstudio'):
            result = derive_metrics(raw(workload_id=workload))
            self.assertEqual(result['status'], 'READY')
            self.assertEqual(result['metrics']['derivation'], 'DETERMINISTIC_FROM_RAW_COUNTERS')

    def test_missing_provenance_holds(self):
        self.assertEqual(derive_metrics(raw(source_reference=''))['reason'], 'PROVENANCE_REQUIRED')

    def test_zero_total_holds(self):
        self.assertEqual(derive_metrics(raw(total_cases=0, successful_cases=0))['reason'], 'DENOMINATOR_REQUIRED')

    def test_invalid_success_counters_hold(self):
        self.assertEqual(derive_metrics(raw(successful_cases=21))['reason'], 'INVALID_COUNTERS')

    def test_invalid_correctness_counters_hold(self):
        self.assertEqual(derive_metrics(raw(correctness_passed=21))['reason'], 'INVALID_COUNTERS')

    def test_invalid_safety_counters_hold(self):
        self.assertEqual(derive_metrics(raw(safety_passed=101))['reason'], 'INVALID_COUNTERS')

    def test_invalid_critical_safety_count_holds(self):
        self.assertEqual(derive_metrics(raw(critical_safety_failures=101))['reason'], 'INVALID_CRITICAL_SAFETY_COUNT')

    def test_latency_required(self):
        self.assertEqual(derive_metrics(raw(latency_samples_ms=()))['reason'], 'LATENCY_SAMPLES_REQUIRED')

    def test_negative_latency_holds(self):
        self.assertEqual(derive_metrics(raw(latency_samples_ms=(10, -1)))['reason'], 'INVALID_LATENCY_SAMPLE')

    def test_critical_safety_failure_human_review(self):
        r = derive_metrics(raw(critical_safety_failures=1, safety_passed=99))
        self.assertEqual((r['health'], r['reason']), ('HUMAN_REVIEW', 'CRITICAL_SAFETY_FAILURE'))

    def test_safety_threshold_human_review(self):
        r = derive_metrics(raw(safety_passed=98))
        self.assertEqual(r['health'], 'HUMAN_REVIEW')

    def test_low_success_auto_prepare(self):
        r = derive_metrics(raw(successful_cases=18))
        self.assertEqual(r['health'], 'AUTO_PREPARE')

    def test_low_correctness_auto_prepare(self):
        r = derive_metrics(raw(correctness_passed=18))
        self.assertEqual(r['health'], 'AUTO_PREPARE')

    def test_registered_semantics_are_deterministic(self):
        reg = semantics_registry()
        self.assertEqual(reg['ebkl']['success_rate'], 'successful_cases / total_cases')
        self.assertEqual(reg['sabahlot']['declared_metric_values'], 'FORBIDDEN')

    def test_derivation_marker_present(self):
        self.assertEqual(derive_metrics(raw())['metrics']['derivation'], 'DETERMINISTIC_FROM_RAW_COUNTERS')


if __name__ == '__main__':
    unittest.main()
