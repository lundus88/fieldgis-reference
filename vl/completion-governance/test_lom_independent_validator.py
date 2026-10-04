import unittest
from independent_validator import ConsensusPolicy, VerifierReport, validate_completion, validate_completion_consensus

APP = 'a' * 64
SRC = 'b' * 64
ART = 'c' * 64


def inventory():
    return {
        'schema': 'vl.acceptance-inventory/1',
        'app_spec_sha256': APP,
        'source_sha256': SRC,
        'items': [
            {'requirement_id':'REQ-1','description':'feature','required':True,'accepted_evidence_types':['test','browser']},
            {'requirement_id':'REQ-2','description':'security','required':True,'accepted_evidence_types':['security']},
        ],
    }


def manifest(entries):
    return {
        'schema': 'vl.acceptance-evidence/1',
        'app_spec_sha256': APP,
        'source_sha256': SRC,
        'artifact_sha256': ART,
        'evidence': entries,
    }


class LOMIndependentValidatorTests(unittest.TestCase):
    def test_complete_independent_evidence_passes(self):
        out = validate_completion(inventory(), manifest([
            {'requirement_id':'REQ-1','evidence_type':'test','state':'PASS','evidence_digest':'sha256:x'},
            {'requirement_id':'REQ-2','evidence_type':'security','state':'PASS','evidence_digest':'sha256:y'},
        ]))
        self.assertEqual(out['status'], 'PASS')
        self.assertFalse(out['builder_self_report_trusted'])
        self.assertTrue(out['production_locked'])

    def test_missing_evidence_holds(self):
        out = validate_completion(inventory(), manifest([
            {'requirement_id':'REQ-1','evidence_type':'test','state':'PASS','evidence_digest':'sha256:x'}
        ]))
        self.assertEqual(out['status'], 'HOLD')

    def test_failed_evidence_fails(self):
        out = validate_completion(inventory(), manifest([
            {'requirement_id':'REQ-1','evidence_type':'test','state':'FAIL','evidence_digest':'sha256:x'},
            {'requirement_id':'REQ-2','evidence_type':'security','state':'PASS','evidence_digest':'sha256:y'},
        ]))
        self.assertEqual(out['status'], 'FAIL')

    def test_builder_self_report_cannot_satisfy_requirement(self):
        out = validate_completion(inventory(), manifest([
            {'requirement_id':'REQ-1','evidence_type':'builder-self-report','state':'PASS','evidence_digest':'sha256:x'},
            {'requirement_id':'REQ-2','evidence_type':'security','state':'PASS','evidence_digest':'sha256:y'},
        ]))
        self.assertEqual(out['status'], 'HOLD')

    def test_binding_mismatch_fails(self):
        m = manifest([])
        m['app_spec_sha256'] = 'd' * 64
        out = validate_completion(inventory(), m)
        self.assertEqual(out['status'], 'FAIL')
        self.assertEqual(out['reason'], 'APP_SPEC_BINDING_MISMATCH')


class LOMVerifierConsensusTests(unittest.TestCase):
    def base_pass(self):
        return validate_completion(inventory(), manifest([
            {'requirement_id':'REQ-1','evidence_type':'test','state':'PASS','evidence_digest':'sha256:x'},
            {'requirement_id':'REQ-2','evidence_type':'security','state':'PASS','evidence_digest':'sha256:y'},
        ]))

    def report(self, validator, method, ref, status='PASS', confidence=0.92, executor='builder-1'):
        base = self.base_pass()
        return VerifierReport(
            validator_id=validator,
            executor_id=executor,
            decision_sha256=base['decision_sha256'],
            status=status,
            evidence_ref=ref,
            evidence_fresh=True,
            confidence=confidence,
            method_id=method,
        )

    def test_two_independent_methods_can_reach_consensus_pass(self):
        base = self.base_pass()
        reports = [
            self.report('validator-a','static-analysis','urn:verify:static'),
            self.report('validator-b','runtime-test','urn:verify:runtime', confidence=0.88),
        ]
        out = validate_completion_consensus(base, reports)
        self.assertEqual(out['status'], 'PASS')
        self.assertEqual(out['reason'], 'INDEPENDENT_CONSENSUS_PASS')
        self.assertTrue(out['high_assurance_verified'])
        self.assertEqual(out['execution_authority'], 'NONE')
        self.assertEqual(out['production_authority'], 'HUMAN_ONLY')
        self.assertEqual(out['protected_main_merge'], 'HUMAN_ONLY')
        self.assertEqual(out['self_approval'], 'FORBIDDEN')

    def test_quorum_shortfall_holds(self):
        base = self.base_pass()
        out = validate_completion_consensus(
            base,
            [self.report('validator-a','static-analysis','urn:verify:static')],
        )
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'VERIFIER_QUORUM_NOT_MET')

    def test_duplicate_validator_identity_holds(self):
        base = self.base_pass()
        out = validate_completion_consensus(base, [
            self.report('validator-a','static-analysis','urn:verify:static'),
            self.report('validator-a','runtime-test','urn:verify:runtime'),
        ])
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'DUPLICATE_VERIFIER_ID')

    def test_self_validation_holds(self):
        base = self.base_pass()
        reports = [
            self.report('builder-1','static-analysis','urn:verify:static', executor='builder-1'),
            self.report('validator-b','runtime-test','urn:verify:runtime'),
        ]
        out = validate_completion_consensus(base, reports)
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'VERIFIER_REPORT_INVALID')
        self.assertIn('builder-1:SELF_VALIDATION_FORBIDDEN', out['errors'])

    def test_negative_finding_cannot_be_outvoted(self):
        base = self.base_pass()
        out = validate_completion_consensus(base, [
            self.report('validator-a','static-analysis','urn:verify:static', status='PASS'),
            self.report('validator-b','runtime-test','urn:verify:runtime', status='FAIL'),
            self.report('validator-c','schema-check','urn:verify:schema', status='PASS'),
        ], policy=ConsensusPolicy(minimum_validators=3, minimum_methods=3))
        self.assertEqual(out['status'], 'FAIL')
        self.assertEqual(out['reason'], 'VERIFIER_NEGATIVE_FINDING')
        self.assertFalse(out['high_assurance_verified'])

    def test_hold_report_prevents_pass(self):
        base = self.base_pass()
        out = validate_completion_consensus(base, [
            self.report('validator-a','static-analysis','urn:verify:static', status='PASS'),
            self.report('validator-b','runtime-test','urn:verify:runtime', status='HOLD'),
        ])
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'VERIFIER_HOLD_OR_DISAGREEMENT')

    def test_method_diversity_is_required(self):
        base = self.base_pass()
        out = validate_completion_consensus(base, [
            self.report('validator-a','same-method','urn:verify:a'),
            self.report('validator-b','same-method','urn:verify:b'),
        ])
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'VERIFIER_METHOD_DIVERSITY_NOT_MET')

    def test_duplicate_evidence_is_not_independent(self):
        base = self.base_pass()
        out = validate_completion_consensus(base, [
            self.report('validator-a','static-analysis','urn:verify:shared'),
            self.report('validator-b','runtime-test','urn:verify:shared'),
        ])
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'VERIFIER_EVIDENCE_NOT_INDEPENDENT')

    def test_confidence_disagreement_holds(self):
        base = self.base_pass()
        out = validate_completion_consensus(base, [
            self.report('validator-a','static-analysis','urn:verify:static', confidence=0.98),
            self.report('validator-b','runtime-test','urn:verify:runtime', confidence=0.60),
        ])
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'VERIFIER_CONFIDENCE_DISAGREEMENT')

    def test_stale_verifier_evidence_holds(self):
        base = self.base_pass()
        a = self.report('validator-a','static-analysis','urn:verify:static')
        b = self.report('validator-b','runtime-test','urn:verify:runtime')
        b = VerifierReport(
            validator_id=b.validator_id,
            executor_id=b.executor_id,
            decision_sha256=b.decision_sha256,
            status=b.status,
            evidence_ref=b.evidence_ref,
            evidence_fresh=False,
            confidence=b.confidence,
            method_id=b.method_id,
        )
        out = validate_completion_consensus(base, [a,b])
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'VERIFIER_REPORT_INVALID')

    def test_consensus_cannot_upgrade_base_hold(self):
        base = validate_completion(inventory(), manifest([
            {'requirement_id':'REQ-1','evidence_type':'test','state':'PASS','evidence_digest':'sha256:x'},
        ]))
        reports = [
            VerifierReport('validator-a','builder-1',base['decision_sha256'],'PASS','urn:verify:a',True,0.9,'static-analysis'),
            VerifierReport('validator-b','builder-1',base['decision_sha256'],'PASS','urn:verify:b',True,0.9,'runtime-test'),
        ]
        out = validate_completion_consensus(base, reports)
        self.assertEqual(out['status'], 'HOLD')
        self.assertEqual(out['reason'], 'BASE_COMPLETION_NOT_PASS')



if __name__ == '__main__':
    unittest.main()
