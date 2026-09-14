import unittest

from planner import RemediationSignal, build_plan, build_remediation_queue, classify

SHA = 'a' * 40


def sig(**overrides):
    data = dict(
        workload_id='ebkl',
        action_class='AUTO_PREPARE',
        reason='PERFORMANCE_IMPROVEMENT_REQUIRED',
        evidence_sha=SHA,
        source_reference='ci://run/123',
        evidence_fresh=True,
        target_action='NON_PRODUCTION_REVERSIBLE_ACTION',
        risk='LOW',
        reversible=True,
        production=False,
    )
    data.update(overrides)
    return RemediationSignal(**data)


class PlannerTests(unittest.TestCase):
    def test_auto_prepare_becomes_prepare_pr(self):
        self.assertEqual(classify(sig())['status'], 'PREPARE_PR')

    def test_stale_evidence_holds(self):
        self.assertEqual(classify(sig(evidence_fresh=False))['status'], 'HOLD')

    def test_missing_sha_holds(self):
        self.assertEqual(classify(sig(evidence_sha=None))['status'], 'HOLD')

    def test_missing_source_holds(self):
        self.assertEqual(classify(sig(source_reference=None))['status'], 'HOLD')

    def test_unknown_action_class_holds(self):
        self.assertEqual(classify(sig(action_class='UNKNOWN'))['status'], 'HOLD')

    def test_unknown_risk_holds(self):
        self.assertEqual(classify(sig(risk='EXTREME'))['status'], 'HOLD')

    def test_high_risk_human_review(self):
        self.assertEqual(classify(sig(risk='HIGH'))['status'], 'HUMAN_REVIEW')

    def test_production_human_review(self):
        self.assertEqual(classify(sig(production=True))['status'], 'HUMAN_REVIEW')

    def test_protected_main_human_review(self):
        self.assertEqual(classify(sig(target_action='PROTECTED_MAIN_MERGE'))['status'], 'HUMAN_REVIEW')

    def test_financial_commitment_human_review(self):
        self.assertEqual(classify(sig(target_action='FINANCIAL_COMMITMENT'))['status'], 'HUMAN_REVIEW')

    def test_irreversible_holds(self):
        self.assertEqual(classify(sig(reversible=False))['status'], 'HOLD')

    def test_upstream_hold_stays_hold(self):
        self.assertEqual(classify(sig(action_class='HOLD'))['status'], 'HOLD')

    def test_upstream_human_review_stays_human_review(self):
        self.assertEqual(classify(sig(action_class='HUMAN_REVIEW'))['status'], 'HUMAN_REVIEW')

    def test_monitor_stays_monitor(self):
        self.assertEqual(classify(sig(action_class='MONITOR'))['status'], 'MONITOR')

    def test_plan_ceiling_and_external_execution(self):
        plan = build_plan(sig())
        self.assertEqual(plan['autonomous_ceiling'], 'PREPARE_PR')
        self.assertEqual(plan['production_authority'], 'HUMAN_ONLY')
        self.assertEqual(plan['external_action_execution'], 'DISABLED')

    def test_queue_prioritizes_hold_then_review_then_prepare(self):
        queue = build_remediation_queue([
            sig(workload_id='c', action_class='AUTO_PREPARE'),
            sig(workload_id='b', risk='HIGH'),
            sig(workload_id='a', evidence_fresh=False),
        ])
        self.assertEqual([p['status'] for p in queue], ['HOLD', 'HUMAN_REVIEW', 'PREPARE_PR'])


if __name__ == '__main__':
    unittest.main()
