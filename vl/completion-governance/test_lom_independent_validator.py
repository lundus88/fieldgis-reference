import unittest
from independent_validator import validate_completion

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


if __name__ == '__main__':
    unittest.main()
