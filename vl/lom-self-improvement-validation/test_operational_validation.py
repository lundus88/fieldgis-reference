import importlib.util
from pathlib import Path
import unittest

RUNTIME_PATH = Path(__file__).resolve().parents[1] / 'lom-self-improvement-runtime' / 'self_improvement_runtime.py'
spec = importlib.util.spec_from_file_location('lom43_runtime', RUNTIME_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

Observation = mod.Observation
CandidateImprovement = mod.CandidateImprovement
EvaluationResult = mod.EvaluationResult
ImprovementLedger = mod.ImprovementLedger
SelfImprovementRuntime = mod.SelfImprovementRuntime


class GoldenOperationalValidation(unittest.TestCase):
    def setUp(self):
        self.runtime = SelfImprovementRuntime()

    def test_golden_01_validated_improvement_reaches_prepare_pr(self):
        obs = Observation('g01-o','PROMPT','READY','golden://01','routing prompt is inefficient')
        self.assertEqual(self.runtime.observe(obs), 'DIAGNOSE')
        candidate = CandidateImprovement('g01-c','PROMPT','tighten routing prompt','LOW',True,False)
        self.assertEqual(self.runtime.stage(candidate), 'SANDBOX')
        result = EvaluationResult(.70,.82,.85,.90,.92,.95,True,True)
        disposition = self.runtime.compare(result)
        self.assertEqual(disposition, 'PREPARE_PR')
        ledger = ImprovementLedger()
        record = self.runtime.record(ledger, obs, candidate, result, disposition)
        self.assertEqual(record.disposition, 'PREPARE_PR')
        self.assertEqual(len(ledger.all()), 1)

    def test_golden_02_missing_evidence_fails_closed(self):
        obs = Observation('g02-o','PROMPT','MISSING','golden://02','weak prompt')
        with self.assertRaisesRegex(ValueError, 'EVIDENCE_NOT_READY'):
            self.runtime.observe(obs)

    def test_golden_03_unknown_target_holds(self):
        c = CandidateImprovement('g03-c','UNREGISTERED_TARGET','x','LOW',True,False)
        self.assertEqual(self.runtime.stage(c), 'HOLD')

    def test_golden_04_high_risk_escalates(self):
        c = CandidateImprovement('g04-c','NON_PROD_CODE','x','HIGH',True,False)
        self.assertEqual(self.runtime.stage(c), 'ESCALATE')

    def test_golden_05_irreversible_holds(self):
        c = CandidateImprovement('g05-c','NON_PROD_CODE','x','LOW',False,False)
        self.assertEqual(self.runtime.stage(c), 'HOLD')

    def test_golden_06_production_escalates(self):
        c = CandidateImprovement('g06-c','NON_PROD_CODE','x','LOW',True,True)
        self.assertEqual(self.runtime.stage(c), 'ESCALATE')

    def test_golden_07_protected_main_escalates(self):
        c = CandidateImprovement('g07-c','PROTECTED_MAIN_MERGE','merge','LOW',True,False)
        self.assertEqual(self.runtime.stage(c), 'ESCALATE')

    def test_golden_08_authority_widening_escalates(self):
        c = CandidateImprovement('g08-c','AUTHORITY_WIDENING','expand','LOW',True,False)
        self.assertEqual(self.runtime.stage(c), 'ESCALATE')

    def test_golden_09_failed_regression_rejects(self):
        r = EvaluationResult(.60,.80,.80,.90,.90,.95,False,True)
        self.assertEqual(self.runtime.compare(r), 'REJECT')

    def test_golden_10_missing_independent_validation_holds(self):
        r = EvaluationResult(.60,.80,.80,.90,.90,.95,True,False)
        self.assertEqual(self.runtime.compare(r), 'HOLD')

    def test_golden_11_correctness_regression_rejects(self):
        r = EvaluationResult(.60,.75,.90,.80,.90,.95,True,True)
        self.assertEqual(self.runtime.compare(r), 'REJECT')

    def test_golden_12_safety_regression_rejects(self):
        r = EvaluationResult(.60,.75,.80,.90,.95,.90,True,True)
        self.assertEqual(self.runtime.compare(r), 'REJECT')

    def test_golden_13_no_measurable_improvement_rejects(self):
        r = EvaluationResult(.80,.80,.90,.90,.95,.95,True,True)
        self.assertEqual(self.runtime.compare(r), 'REJECT')

    def test_golden_14_self_merge_forbidden(self):
        with self.assertRaisesRegex(PermissionError, 'SELF_APPROVAL_FORBIDDEN'):
            self.runtime.apply_to_protected_main()

    def test_golden_15_self_production_release_forbidden(self):
        with self.assertRaisesRegex(PermissionError, 'PRODUCTION_RELEASE_REQUIRES_HUMAN'):
            self.runtime.deploy_production()


if __name__ == '__main__':
    unittest.main()
