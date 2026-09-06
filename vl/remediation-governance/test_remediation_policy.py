import unittest
from remediation_policy import authorize


GRANT = {
    'capabilities': ['pr.inspect', 'pr.remediate', 'ci.inspect', 'ci.repair', 'merge.prepare'],
    'protected_branches': ['main'],
}


class RemediationPolicyTests(unittest.TestCase):
    def test_branch_remediation_allowed(self):
        out = authorize({'capability':'pr.remediate','target_branch':'fix/test'}, GRANT)
        self.assertEqual(out['decision'],'ALLOW')
        self.assertEqual(out['authority'],'branch_scoped')
        self.assertFalse(out['merge_executed'])

    def test_protected_branch_repair_denied(self):
        out = authorize({'capability':'ci.repair','target_branch':'main'}, GRANT)
        self.assertEqual(out['decision'],'DENY')
        self.assertEqual(out['reason'],'PROTECTED_BRANCH_MUTATION_BLOCKED')

    def test_merge_execute_always_denied(self):
        out = authorize({'capability':'merge.execute','target_branch':'main'}, {**GRANT,'capabilities':GRANT['capabilities']+['merge.execute']})
        self.assertEqual(out['decision'],'DENY')
        self.assertEqual(out['reason'],'FORBIDDEN_CAPABILITY')

    def test_production_approve_always_denied(self):
        out = authorize({'capability':'production.approve','target_branch':'main'}, GRANT)
        self.assertEqual(out['decision'],'DENY')
        self.assertTrue(out['production_locked'])

    def test_merge_prepare_is_recommendation_only(self):
        out = authorize({'capability':'merge.prepare','target_branch':'main'}, GRANT)
        self.assertEqual(out['decision'],'ALLOW')
        self.assertEqual(out['authority'],'recommendation_only')
        self.assertFalse(out['merge_executed'])

    def test_ungranted_capability_denied(self):
        out = authorize({'capability':'ci.repair','target_branch':'fix/test'}, {'capabilities':['ci.inspect'],'protected_branches':['main']})
        self.assertEqual(out['decision'],'DENY')
        self.assertEqual(out['reason'],'CAPABILITY_NOT_GRANTED')


if __name__ == '__main__':
    unittest.main()
