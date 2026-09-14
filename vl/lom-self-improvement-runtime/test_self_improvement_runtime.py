import unittest
from self_improvement_runtime import (
    Observation, CandidateImprovement, EvaluationResult,
    ImprovementLedger, SelfImprovementRuntime
)

class SelfImprovementRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = SelfImprovementRuntime()

    def test_observation_requires_ready_evidence(self):
        obs = Observation('o1','PROMPT','MISSING','ev1','weak prompt')
        with self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_READY'):
            self.runtime.observe(obs)

    def test_observation_requires_evidence_reference(self):
        obs = Observation('o1','PROMPT','READY','','weak prompt')
        with self.assertRaisesRegex(ValueError,'EVIDENCE_REFERENCE_REQUIRED'):
            self.runtime.observe(obs)

    def test_low_risk_reversible_non_prod_is_delegated_to_sandbox(self):
        c = CandidateImprovement('c1','NON_PROD_CODE','fix','LOW',True,False)
        self.assertEqual(self.runtime.stage(c),'SANDBOX')

    def test_unknown_target_fails_closed(self):
        c = CandidateImprovement('c1','UNKNOWN','fix','LOW',True,False)
        self.assertEqual(self.runtime.stage(c),'HOLD')

    def test_high_risk_escalates(self):
        c = CandidateImprovement('c1','NON_PROD_CODE','fix','HIGH',True,False)
        self.assertEqual(self.runtime.stage(c),'ESCALATE')

    def test_irreversible_candidate_is_held(self):
        c = CandidateImprovement('c1','NON_PROD_CODE','fix','LOW',False,False)
        self.assertEqual(self.runtime.stage(c),'HOLD')

    def test_production_boundary_escalates(self):
        c = CandidateImprovement('c1','NON_PROD_CODE','fix','LOW',True,True)
        self.assertEqual(self.runtime.stage(c),'ESCALATE')

    def test_human_only_target_escalates(self):
        c = CandidateImprovement('c1','PROTECTED_MAIN_MERGE','merge','LOW',True,False)
        self.assertEqual(self.runtime.stage(c),'ESCALATE')

    def test_compare_requires_regression_pass(self):
        r = EvaluationResult(.6,.9,.8,.9,.9,.9,False,True)
        self.assertEqual(self.runtime.compare(r),'REJECT')

    def test_compare_requires_independent_validation(self):
        r = EvaluationResult(.6,.9,.8,.9,.9,.9,True,False)
        self.assertEqual(self.runtime.compare(r),'HOLD')

    def test_correctness_regression_is_rejected(self):
        r = EvaluationResult(.6,.7,.8,.7,.9,.9,True,True)
        self.assertEqual(self.runtime.compare(r),'REJECT')

    def test_safety_regression_is_rejected(self):
        r = EvaluationResult(.6,.7,.8,.9,.9,.8,True,True)
        self.assertEqual(self.runtime.compare(r),'REJECT')

    def test_verified_improvement_prepares_pr_only(self):
        r = EvaluationResult(.6,.8,.8,.9,.9,.95,True,True)
        self.assertEqual(self.runtime.compare(r),'PREPARE_PR')

    def test_ledger_records_delta_and_evidence(self):
        ledger = ImprovementLedger()
        obs = Observation('o1','PROMPT','READY','ev://1','weak prompt')
        c = CandidateImprovement('c1','PROMPT','tighten','LOW',True,False)
        r = EvaluationResult(.6,.8,.8,.9,.9,.95,True,True)
        rec = self.runtime.record(ledger,obs,c,r,'PREPARE_PR')
        self.assertEqual(rec.delta,.2)
        self.assertEqual(rec.evidence_ref,'ev://1')
        self.assertEqual(len(ledger.all()),1)

    def test_protected_main_merge_is_human_only(self):
        with self.assertRaisesRegex(PermissionError,'SELF_APPROVAL_FORBIDDEN'):
            self.runtime.apply_to_protected_main()

    def test_production_release_is_human_only(self):
        with self.assertRaisesRegex(PermissionError,'PRODUCTION_RELEASE_REQUIRES_HUMAN'):
            self.runtime.deploy_production()

    def test_authority_widening_is_human_only(self):
        c = CandidateImprovement('c1','AUTHORITY_WIDENING','expand','LOW',True,False)
        self.assertEqual(self.runtime.stage(c),'ESCALATE')

if __name__ == '__main__':
    unittest.main()
