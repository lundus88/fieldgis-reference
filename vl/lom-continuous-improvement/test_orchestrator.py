import unittest
from orchestrator import ImprovementSignal, ContinuousImprovementOrchestrator

class ContinuousImprovementOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.o = ContinuousImprovementOrchestrator()

    def signal(self, **overrides):
        data = dict(
            signal_id='s1', target='NON_PROD_CODE', evidence_state='READY', evidence_ref='ev://1',
            problem='regression gap', impact=.8, confidence=.9, risk='LOW', reversible=True, production=False
        )
        data.update(overrides)
        return ImprovementSignal(**data)

    def test_ready_low_risk_is_qualified(self):
        d = self.o.qualify(self.signal())
        self.assertEqual(d.disposition, 'QUALIFIED')
        self.assertEqual(self.o.next_action(d), 'STAGE_IN_SANDBOX')

    def test_missing_evidence_holds(self):
        d = self.o.qualify(self.signal(evidence_state='MISSING'))
        self.assertEqual((d.disposition, d.reason), ('HOLD','EVIDENCE_NOT_READY'))

    def test_missing_evidence_reference_holds(self):
        d = self.o.qualify(self.signal(evidence_ref=''))
        self.assertEqual(d.reason, 'EVIDENCE_REFERENCE_REQUIRED')

    def test_unknown_target_holds(self):
        d = self.o.qualify(self.signal(target='UNKNOWN'))
        self.assertEqual(d.reason, 'UNKNOWN_TARGET')

    def test_human_only_escalates(self):
        d = self.o.qualify(self.signal(target='PROTECTED_MAIN_MERGE'))
        self.assertEqual(d.disposition, 'ESCALATE')
        self.assertEqual(self.o.next_action(d), 'HUMAN_REVIEW')

    def test_production_escalates(self):
        d = self.o.qualify(self.signal(production=True))
        self.assertEqual(d.reason, 'PRODUCTION_BOUNDARY')

    def test_high_risk_escalates(self):
        d = self.o.qualify(self.signal(risk='HIGH'))
        self.assertEqual(d.reason, 'HIGH_RISK')

    def test_irreversible_holds(self):
        d = self.o.qualify(self.signal(reversible=False))
        self.assertEqual(d.reason, 'REVERSIBILITY_REQUIRED')

    def test_unknown_risk_holds(self):
        d = self.o.qualify(self.signal(risk='UNKNOWN'))
        self.assertEqual(d.reason, 'UNKNOWN_RISK')

    def test_score_out_of_range_holds(self):
        d = self.o.qualify(self.signal(impact=1.1))
        self.assertEqual(d.reason, 'SCORE_OUT_OF_RANGE')

    def test_prioritization_is_deterministic(self):
        a = self.signal(signal_id='a', impact=.9, confidence=.9)
        b = self.signal(signal_id='b', impact=.6, confidence=.7)
        q, blocked = self.o.prioritize([b,a])
        self.assertEqual([x.signal_id for x in q], ['a','b'])
        self.assertEqual(blocked, [])

    def test_medium_risk_penalty_applies(self):
        low = self.o.qualify(self.signal(signal_id='l', risk='LOW'))
        med = self.o.qualify(self.signal(signal_id='m', risk='MEDIUM'))
        self.assertGreater(low.priority, med.priority)

    def test_failed_regression_rejects(self):
        self.assertEqual(self.o.finalize_validation(False,True,False,False,True),'REJECT')

    def test_missing_independent_validation_holds(self):
        self.assertEqual(self.o.finalize_validation(True,False,False,False,True),'HOLD')

    def test_correctness_regression_rejects(self):
        self.assertEqual(self.o.finalize_validation(True,True,True,False,True),'REJECT')

    def test_safety_regression_rejects(self):
        self.assertEqual(self.o.finalize_validation(True,True,False,True,True),'REJECT')

    def test_no_measurable_improvement_rejects(self):
        self.assertEqual(self.o.finalize_validation(True,True,False,False,False),'REJECT')

    def test_validated_candidate_prepares_pr_only(self):
        self.assertEqual(self.o.finalize_validation(True,True,False,False,True),'PREPARE_PR')

    def test_protected_main_merge_is_human_only(self):
        with self.assertRaisesRegex(PermissionError,'HUMAN_APPROVAL_REQUIRED'):
            self.o.merge_protected_main()

    def test_production_release_is_human_only(self):
        with self.assertRaisesRegex(PermissionError,'HUMAN_APPROVAL_REQUIRED'):
            self.o.deploy_production()

if __name__ == '__main__':
    unittest.main()
