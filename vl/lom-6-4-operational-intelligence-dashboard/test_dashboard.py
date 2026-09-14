import unittest

from dashboard import WorkloadSnapshot, build_director_view, classify_snapshot, workload_card


def snap(**overrides):
    data = dict(
        workload_id='ebkl',
        status='READY',
        health='MONITOR',
        reason='TECHNICAL_EVIDENCE_READY',
        evidence_sha='a' * 40,
        source_reference='ci://run/1',
        sample_count=10,
        success_rate=.99,
        correctness=.98,
        safety=.999,
        p95_latency_ms=1200,
        evidence_fresh=True,
    )
    data.update(overrides)
    return WorkloadSnapshot(**data)


class DashboardTests(unittest.TestCase):
    def test_monitor_ready(self):
        self.assertEqual(classify_snapshot(snap())['action_class'], 'MONITOR')

    def test_not_ready_holds(self):
        self.assertEqual(classify_snapshot(snap(status='HOLD', reason='SOURCE_EVIDENCE_MISSING'))['action_class'], 'HOLD')

    def test_stale_holds(self):
        self.assertEqual(classify_snapshot(snap(evidence_fresh=False))['reason'], 'EVIDENCE_NOT_FRESH')

    def test_missing_sha_holds(self):
        self.assertEqual(classify_snapshot(snap(evidence_sha=None))['reason'], 'EVIDENCE_PROVENANCE_REQUIRED')

    def test_missing_source_holds(self):
        self.assertEqual(classify_snapshot(snap(source_reference=None))['reason'], 'EVIDENCE_PROVENANCE_REQUIRED')

    def test_sample_count_holds(self):
        self.assertEqual(classify_snapshot(snap(sample_count=0))['reason'], 'SAMPLE_COUNT_REQUIRED')

    def test_invalid_rate_holds(self):
        self.assertEqual(classify_snapshot(snap(success_rate=1.1))['reason'], 'VALID_TECHNICAL_RATES_REQUIRED')

    def test_invalid_latency_holds(self):
        self.assertEqual(classify_snapshot(snap(p95_latency_ms=-1))['reason'], 'VALID_LATENCY_REQUIRED')

    def test_unknown_health_holds(self):
        self.assertEqual(classify_snapshot(snap(health='GREEN'))['reason'], 'UNKNOWN_HEALTH_STATE')

    def test_safety_review_preserved(self):
        self.assertEqual(classify_snapshot(snap(health='HUMAN_REVIEW', reason='SAFETY_THRESHOLD_BREACH'))['action_class'], 'HUMAN_REVIEW')

    def test_auto_prepare_preserved(self):
        self.assertEqual(classify_snapshot(snap(health='AUTO_PREPARE'))['action_class'], 'AUTO_PREPARE')

    def test_card_has_score_when_ready(self):
        self.assertIsNotNone(workload_card(snap())['technical_score'])

    def test_hold_card_has_no_score(self):
        card = workload_card(snap(status='HOLD', reason='SOURCE_EVIDENCE_MISSING'))
        self.assertIsNone(card['technical_score'])

    def test_director_view_prioritizes_hold(self):
        view = build_director_view([
            snap(workload_id='sabahlot'),
            snap(workload_id='ebkl', status='HOLD', reason='SOURCE_EVIDENCE_MISSING'),
        ])
        self.assertEqual(view['overall_action_class'], 'HOLD')
        self.assertEqual(view['workloads'][0]['workload_id'], 'ebkl')

    def test_director_view_counts(self):
        view = build_director_view([
            snap(workload_id='ebkl'),
            snap(workload_id='sabahlot', health='AUTO_PREPARE'),
            snap(workload_id='lunduslead', health='HUMAN_REVIEW'),
        ])
        self.assertEqual(view['counts']['MONITOR'], 1)
        self.assertEqual(view['counts']['AUTO_PREPARE'], 1)
        self.assertEqual(view['counts']['HUMAN_REVIEW'], 1)

    def test_authority_boundaries_exposed(self):
        view = build_director_view([snap()])
        self.assertEqual(view['autonomous_ceiling'], 'PREPARE_PR')
        self.assertEqual(view['production_authority'], 'HUMAN_ONLY')


if __name__ == '__main__':
    unittest.main()
