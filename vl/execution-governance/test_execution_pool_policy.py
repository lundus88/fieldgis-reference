import unittest
from execution_pool_policy import authorize_execution, attest_artifact


POOL={
  'pool_id':'sandbox-linux-x64',
  'profile_version':'1.0.0',
  'image_digest':'sha256:'+'1'*64,
  'network_policy':'egress-restricted',
  'cpu_limit':2,
  'memory_mb_limit':4096,
  'allowed_capabilities':['build.execute','test.execute'],
  'ambient_production_credentials':False,
  'status':'certified',
}


class ExecutionPoolTests(unittest.TestCase):
    def test_certified_pool_allows_bounded_execution(self):
        out=authorize_execution(POOL,{'capability':'build.execute','cpu':2,'memory_mb':2048,'network_policy':'egress-restricted'})
        self.assertEqual(out['decision'],'ALLOW')
        self.assertFalse(out['production_credentials_available'])

    def test_unknown_pool_is_denied(self):
        bad={**POOL,'status':'unknown'}
        out=authorize_execution(bad,{'capability':'build.execute','cpu':1,'memory_mb':1024})
        self.assertEqual(out['reason'],'UNCERTIFIED_EXECUTION_POOL')

    def test_ambient_production_credentials_are_denied(self):
        bad={**POOL,'ambient_production_credentials':True}
        out=authorize_execution(bad,{'capability':'build.execute','cpu':1,'memory_mb':1024})
        self.assertEqual(out['reason'],'AMBIENT_PRODUCTION_CREDENTIALS_FORBIDDEN')

    def test_resource_ceiling_is_enforced(self):
        out=authorize_execution(POOL,{'capability':'build.execute','cpu':8,'memory_mb':2048})
        self.assertEqual(out['reason'],'CPU_LIMIT_EXCEEDED')

    def test_capability_binding_is_enforced(self):
        out=authorize_execution(POOL,{'capability':'production.deploy','cpu':1,'memory_mb':1024})
        self.assertEqual(out['reason'],'CAPABILITY_NOT_BOUND_TO_POOL')

    def test_certified_artifact_attestation_records_pool_profile(self):
        out=attest_artifact(POOL,'a'*64)
        self.assertTrue(out['promotable'])
        self.assertEqual(out['pool_id'],POOL['pool_id'])
        self.assertEqual(out['profile_version'],POOL['profile_version'])
        self.assertEqual(out['image_digest'],POOL['image_digest'])
        self.assertTrue(out['production_locked'])

    def test_uncertified_pool_cannot_make_promotable_artifact(self):
        out=attest_artifact({**POOL,'status':'uncertified'},'a'*64)
        self.assertFalse(out['promotable'])


if __name__=='__main__':
    unittest.main()
