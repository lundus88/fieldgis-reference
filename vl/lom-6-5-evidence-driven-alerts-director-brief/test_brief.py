import unittest

from brief import DirectorSignal, build_director_brief, classify_signal


def s(**overrides):
    base = dict(
        workload_id='ebkl',
        action_class='MONITOR',
        reason='TECHNICAL_HEALTHY',
        evidence_sha='a' * 40,
        source_reference='ci://run/1',
        evidence_fresh=True,
        technical_score=95.0,
    )
    base.update(overrides)
    return DirectorSignal(**base)


class BriefTests(unittest.TestCase):
    def test_monitor_signal(self):
        self.assertEqual(classify_signal(s())['action_class'], 'MONITOR')

    def test_missing_workload_holds(self):
        self.assertEqual(classify_signal(s(workload_id=''))['reason'], 'WORKLOAD_ID_REQUIRED')

    def test_unknown_action_holds(self):
        self.assertEqual(classify_signal(s(action_class='RUN'))['reason'], 'UNKNOWN_ACTION_CLASS')

    def test_stale_evidence_holds(self):
        self.assertEqual(classify_signal(s(evidence_fresh=False))['reason'], 'EVIDENCE_NOT_FRESH')

    def test_missing_sha_holds(self):
        self.assertEqual(classify_signal(s(evidence_sha=None))['reason'], 'EVIDENCE_PROVENANCE_REQUIRED')

    def test_missing_source_holds(self):
        self.assertEqual(classify_signal(s(source_reference=None))['reason'], 'EVIDENCE_PROVENANCE_REQUIRED')

    def test_negative_score_holds(self):
        self.assertEqual(classify_signal(s(technical_score=-1))['reason'], 'INVALID_TECHNICAL_SCORE')

    def test_score_over_100_holds(self):
        self.assertEqual(classify_signal(s(technical_score=101))['reason'], 'INVALID_TECHNICAL_SCORE')

    def test_none_score_allowed(self):
        self.assertEqual(classify_signal(s(technical_score=None))['action_class'], 'MONITOR')

    def test_hold_priority_first(self):
        view = build_director_brief([s(workload_id='b'), s(workload_id='a', action_class='HOLD')])
        self.assertEqual(view['exceptions'][0]['workload_id'], 'a')

    def test_human_review_before_auto_prepare(self):
        view = build_director_brief([
            s(workload_id='auto', action_class='AUTO_PREPARE'),
            s(workload_id='human', action_class='HUMAN_REVIEW'),
        ])
        self.assertEqual(view['exceptions'][0]['workload_id'], 'human')

    def test_overall_hold(self):
        view = build_director_brief([s(), s(workload_id='x', action_class='HOLD')])
        self.assertEqual(view['overall_action_class'], 'HOLD')

    def test_overall_human_review(self):
        view = build_director_brief([s(), s(workload_id='x', action_class='HUMAN_REVIEW')])
        self.assertEqual(view['overall_action_class'], 'HUMAN_REVIEW')

    def test_empty_is_monitor(self):
        self.assertEqual(build_director_brief([])['overall_action_class'], 'MONITOR')

    def test_autonomous_ceiling(self):
        self.assertEqual(build_director_brief([])['autonomous_ceiling'], 'PREPARE_PR')

    def test_external_messaging_disabled(self):
        self.assertEqual(build_director_brief([])['external_messaging'], 'DISABLED')


if __name__ == '__main__':
    unittest.main()
