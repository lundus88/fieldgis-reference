import unittest
from learning_core import (
    DecisionCorpus, DecisionRecord, HumanCorrectionLog, CorrectionRecord,
    GoldenScenarioRegistry, GoldenScenario, OutcomeScore, LearningEngine
)

class LearningCoreTests(unittest.TestCase):
    def test_decision_corpus_append(self):
        c=DecisionCorpus(); r=DecisionRecord('d1','RUN_TEST','READY','PASS','APPROVED','ok')
        c.append(r); self.assertEqual(len(c.all()),1)

    def test_duplicate_decision_rejected(self):
        c=DecisionCorpus(); r=DecisionRecord('d1','RUN_TEST','READY','PASS','APPROVED','ok')
        c.append(r)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_DECISION_ID'): c.append(r)

    def test_correction_requires_rationale(self):
        log=HumanCorrectionLog()
        with self.assertRaisesRegex(ValueError,'RATIONALE_REQUIRED'):
            log.append(CorrectionRecord('c1','d1','DELEGATE','HOLD',''))

    def test_duplicate_correction_rejected(self):
        log=HumanCorrectionLog(); r=CorrectionRecord('c1','d1','DELEGATE','HOLD','missing evidence')
        log.append(r)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_CORRECTION_ID'): log.append(r)

    def test_golden_scenario_version_monotonic(self):
        reg=GoldenScenarioRegistry()
        reg.register(GoldenScenario('g1','unknown_action','HOLD',('DEFAULT_DENY',),1))
        with self.assertRaisesRegex(ValueError,'NON_MONOTONIC_VERSION'):
            reg.register(GoldenScenario('g1','unknown_action','HOLD',('DEFAULT_DENY',),1))

    def test_outcome_score_bounds(self):
        with self.assertRaisesRegex(ValueError,'SCORE_OUT_OF_RANGE'):
            OutcomeScore(1.2,1,1,1,1).validate()

    def test_weighting_prioritizes_correctness_and_safety(self):
        s=OutcomeScore(1,1,0,0,0)
        self.assertEqual(s.weighted,0.6)

    def test_learning_proposal_is_propose_only(self):
        p=LearningEngine().propose('p1','MODEL_ROUTING','prefer stronger model',('d1',),0.9,'READY')
        self.assertEqual(p.disposition,'PROPOSE_ONLY')

    def test_missing_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_READY'):
            LearningEngine().propose('p1','MODEL_ROUTING','x',('d1',),0.8,'MISSING')

    def test_contradictory_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_READY'):
            LearningEngine().propose('p1','MODEL_ROUTING','x',('d1',),0.8,'CONTRADICTORY')

    def test_stale_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_READY'):
            LearningEngine().propose('p1','MODEL_ROUTING','x',('d1',),0.8,'STALE')

    def test_unknown_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_READY'):
            LearningEngine().propose('p1','MODEL_ROUTING','x',('d1',),0.8,'UNKNOWN')

    def test_supporting_evidence_required(self):
        with self.assertRaisesRegex(ValueError,'SUPPORTING_EVIDENCE_REQUIRED'):
            LearningEngine().propose('p1','MODEL_ROUTING','x',tuple(),0.8,'READY')

    def test_confidence_bounds(self):
        with self.assertRaisesRegex(ValueError,'CONFIDENCE_OUT_OF_RANGE'):
            LearningEngine().propose('p1','MODEL_ROUTING','x',('d1',),1.1,'READY')

    def test_production_release_cannot_be_learned_into_authority(self):
        with self.assertRaisesRegex(PermissionError,'AUTHORITY_CHANGE_REQUIRES_HUMAN'):
            LearningEngine().propose('p1','PRODUCTION_RELEASE','auto release',('d1',),1,'READY')

    def test_main_merge_cannot_be_learned_into_authority(self):
        with self.assertRaisesRegex(PermissionError,'AUTHORITY_CHANGE_REQUIRES_HUMAN'):
            LearningEngine().propose('p1','PROTECTED_MAIN_MERGE','auto merge',('d1',),1,'READY')

    def test_financial_commitment_cannot_be_learned_into_authority(self):
        with self.assertRaisesRegex(PermissionError,'AUTHORITY_CHANGE_REQUIRES_HUMAN'):
            LearningEngine().propose('p1','FINANCIAL_COMMITMENT','auto spend',('d1',),1,'READY')

    def test_bid_submission_cannot_be_learned_into_authority(self):
        with self.assertRaisesRegex(PermissionError,'AUTHORITY_CHANGE_REQUIRES_HUMAN'):
            LearningEngine().propose('p1','BID_SUBMISSION','auto submit',('d1',),1,'READY')

    def test_pricing_commitment_cannot_be_learned_into_authority(self):
        with self.assertRaisesRegex(PermissionError,'AUTHORITY_CHANGE_REQUIRES_HUMAN'):
            LearningEngine().propose('p1','PRICING_COMMITMENT','auto quote',('d1',),1,'READY')

    def test_contract_commitment_cannot_be_learned_into_authority(self):
        with self.assertRaisesRegex(PermissionError,'AUTHORITY_CHANGE_REQUIRES_HUMAN'):
            LearningEngine().propose('p1','CONTRACT_COMMITMENT','auto sign',('d1',),1,'READY')

    def test_self_apply_is_forbidden(self):
        eng=LearningEngine(); p=eng.propose('p1','MODEL_ROUTING','x',('d1',),0.8,'READY')
        with self.assertRaisesRegex(PermissionError,'SELF_APPLY_FORBIDDEN'): eng.apply(p)

if __name__=='__main__': unittest.main()
