import unittest
from remediation_policy import authorize

FAILURE_SHA = 'a' * 64
GRANT = {
    'capabilities': ['pr.inspect', 'pr.remediate', 'ci.inspect', 'ci.repair', 'merge.prepare'],
    'protected_branches': ['main'],
    'max_remediation_attempts': 2,
}


class RemediationPolicyTests(unittest.TestCase):
    def test_branch_remediation_allowed_with_evidence(self):
        out = authorize({
            'capability': 'pr.remediate',
            'target_branch': 'fix/test',
            'attempt': 1,
            'failure_evidence_sha256': FAILURE_SHA,
        }, GRANT)
        self.assertEqual(out['decision'], 'ALLOW')
        self.assertEqual(out['authority'], 'branch_scoped')
        self.assertFalse(out['merge_executed'])
        self.assertTrue(out['production_locked'])

    def test_protected_branch_repair_denied(self):
        out = authorize({
            'capability': 'ci.repair',
            'target_branch': 'main',
            'attempt': 1,
            'failure_evidence_sha256': FAILURE_SHA,
        }, GRANT)
        self.assertEqual(out['reason'], 'PROTECTED_BRANCH_MUTATION_BLOCKED')

    def test_retry_budget_exhaustion_denied(self):
        out = authorize({
            'capability': 'ci.repair',
            'target_branch': 'fix/test',
            'attempt': 3,
            'failure_evidence_sha256': FAILURE_SHA,
        }, GRANT)
        self.assertEqual(out['reason'], 'REMEDIATION_BUDGET_EXHAUSTED')

    def test_missing_failure_evidence_denied(self):
        out = authorize({
            'capability': 'pr.remediate',
            'target_branch': 'fix/test',
            'attempt': 1,
        }, GRANT)
        self.assertEqual(out['reason'], 'FAILURE_EVIDENCE_REQUIRED')

    def test_merge_execute_always_denied(self):
        out = authorize({'capability': 'merge.execute', 'target_branch': 'main'}, {**GRANT, 'capabilities': GRANT['capabilities'] + ['merge.execute']})
        self.assertEqual(out['reason'], 'FORBIDDEN_CAPABILITY')

    def test_production_approve_always_denied(self):
        out = authorize({'capability': 'production.approve', 'target_branch': 'main'}, GRANT)
        self.assertEqual(out['decision'], 'DENY')
        self.assertTrue(out['production_locked'])

    def test_production_deploy_always_denied(self):
        out = authorize({'capability': 'production.deploy', 'target_branch': 'main'}, GRANT)
        self.assertEqual(out['reason'], 'FORBIDDEN_CAPABILITY')

    def test_merge_prepare_is_recommendation_only(self):
        out = authorize({'capability': 'merge.prepare', 'target_branch': 'main'}, GRANT)
        self.assertEqual(out['decision'], 'ALLOW')
        self.assertEqual(out['authority'], 'recommendation_only')
        self.assertFalse(out['merge_executed'])


if __name__ == '__main__':
    unittest.main()
