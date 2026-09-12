import unittest

from execution_pool_policy import authorize_execution, attest_release_candidate


POOL = {
    'pool_id': 'lom-sandbox-linux-x64',
    'profile_version': '1.0.0',
    'image_digest': 'sha256:' + '1' * 64,
    'network_policy': 'egress-restricted',
    'cpu_limit': 2,
    'memory_mb_limit': 4096,
    'allowed_capabilities': ['build.execute', 'test.execute'],
    'ambient_production_credentials': False,
    'status': 'certified',
}


class LOMExecutionPoolTests(unittest.TestCase):
    def test_certified_staging_execution_is_allowed(self):
        out = authorize_execution(POOL, {
            'target_environment': 'staging',
            'capability': 'build.execute',
            'cpu': 2,
            'memory_mb': 2048,
            'network_policy': 'egress-restricted',
        })
        self.assertEqual(out['decision'], 'ALLOW')
        self.assertTrue(out['production_locked'])
        self.assertFalse(out['production_credentials_available'])

    def test_production_environment_is_denied(self):
        out = authorize_execution(POOL, {
            'target_environment': 'production',
            'capability': 'build.execute',
            'cpu': 1,
            'memory_mb': 1024,
            'network_policy': 'egress-restricted',
        })
        self.assertEqual(out['decision'], 'DENY')
        self.assertEqual(out['reason'], 'NONPRODUCTION_ENVIRONMENT_REQUIRED')

    def test_uncertified_pool_is_denied(self):
        bad = {**POOL, 'status': 'unknown'}
        out = authorize_execution(bad, {
            'target_environment': 'development',
            'capability': 'build.execute',
            'cpu': 1,
            'memory_mb': 1024,
            'network_policy': 'egress-restricted',
        })
        self.assertEqual(out['reason'], 'UNCERTIFIED_EXECUTION_POOL')

    def test_ambient_production_credentials_are_denied(self):
        bad = {**POOL, 'ambient_production_credentials': True}
        out = authorize_execution(bad, {
            'target_environment': 'development',
            'capability': 'build.execute',
            'cpu': 1,
            'memory_mb': 1024,
            'network_policy': 'egress-restricted',
        })
        self.assertEqual(out['reason'], 'AMBIENT_PRODUCTION_CREDENTIALS_FORBIDDEN')

    def test_resource_ceiling_is_enforced(self):
        out = authorize_execution(POOL, {
            'target_environment': 'development',
            'capability': 'build.execute',
            'cpu': 8,
            'memory_mb': 1024,
            'network_policy': 'egress-restricted',
        })
        self.assertEqual(out['reason'], 'CPU_LIMIT_EXCEEDED')

    def test_capability_binding_is_enforced(self):
        out = authorize_execution(POOL, {
            'target_environment': 'development',
            'capability': 'production.deploy',
            'cpu': 1,
            'memory_mb': 1024,
            'network_policy': 'egress-restricted',
        })
        self.assertEqual(out['reason'], 'CAPABILITY_NOT_BOUND_TO_POOL')

    def test_network_policy_mismatch_is_denied(self):
        out = authorize_execution(POOL, {
            'target_environment': 'development',
            'capability': 'test.execute',
            'cpu': 1,
            'memory_mb': 1024,
            'network_policy': 'open-egress',
        })
        self.assertEqual(out['reason'], 'NETWORK_POLICY_MISMATCH')

    def test_release_candidate_attestation_is_nonproduction_only(self):
        out = attest_release_candidate(POOL, 'a' * 64, 'staging')
        self.assertTrue(out['release_candidate_eligible'])
        self.assertFalse(out['production_approval'])
        self.assertTrue(out['production_locked'])

        prod = attest_release_candidate(POOL, 'a' * 64, 'production')
        self.assertFalse(prod['release_candidate_eligible'])
        self.assertEqual(prod['reason'], 'NONPRODUCTION_ENVIRONMENT_REQUIRED')


if __name__ == '__main__':
    unittest.main()
