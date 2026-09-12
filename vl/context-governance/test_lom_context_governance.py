import json
import unittest
from pathlib import Path

from validate_context_policy import validate_policy, decide
from build_context_manifest import build_context
from pre_model_invocation import ContextGovernanceBlocked, build_pre_model_payload

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT / 'default-context-policy.json').read_text())


class LOMContextGovernanceTests(unittest.TestCase):
    def test_default_deny_and_secret_exclusion(self):
        self.assertTrue(validate_policy(POLICY))
        self.assertEqual(decide(POLICY, 'repo_path', 'docs/private.md', 'internal')['decision'], 'deny')
        self.assertEqual(decide(POLICY, 'repo_path', 'src/.env.production', 'source_code')['decision'], 'deny')

    def test_denied_content_never_crosses_boundary(self):
        resources = [
            {'resource_type':'repo_path','resource':'src/app.ts','data_class':'source_code','content':'SAFE'},
            {'resource_type':'repo_path','resource':'src/.env.production','data_class':'secret','content':'TOP_SECRET'},
        ]
        payload = build_pre_model_payload(policy_path=ROOT / 'default-context-policy.json', resources=resources, task={'kind':'implementation'})
        encoded = json.dumps(payload, sort_keys=True)
        self.assertIn('SAFE', encoded)
        self.assertNotIn('TOP_SECRET', encoded)
        self.assertTrue(payload['production_locked'])
        self.assertFalse(payload['raw_candidates_forwarded'])
        self.assertFalse(payload['context_manifest']['secret_values_recorded'])

    def test_all_denied_blocks_model_boundary(self):
        resources = [{'resource_type':'connector_resource','resource':'production/database/customers','data_class':'production_data','content':'PRIVATE'}]
        with self.assertRaisesRegex(ContextGovernanceBlocked, 'CONTEXT_GOVERNANCE_BLOCKED'):
            build_pre_model_payload(policy_path=ROOT / 'default-context-policy.json', resources=resources, task={'kind':'analysis'})

    def test_manifest_hashes_denied_content_without_recording_value(self):
        secret = 'DO_NOT_RECORD'
        result = build_context(POLICY, [{'resource_type':'repo_path','resource':'src/secrets/key.txt','data_class':'secret','content':secret}])
        encoded = json.dumps(result['manifest'])
        self.assertNotIn(secret, encoded)
        self.assertEqual(len(result['manifest']['resource_decisions'][0]['content_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
