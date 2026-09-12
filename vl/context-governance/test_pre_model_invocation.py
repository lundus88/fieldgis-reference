import json
import unittest
from pathlib import Path

from pre_model_invocation import ContextGovernanceBlocked, build_pre_model_payload


HERE = Path(__file__).resolve().parent
POLICY = HERE / 'default-context-policy.json'


class PreModelInvocationTests(unittest.TestCase):
    def test_allowed_context_crosses_boundary_and_denied_secret_does_not(self):
        resources = [
            {
                'resource_type': 'repo_path',
                'resource': 'src/architecture.ts',
                'data_class': 'source_code',
                'content': 'SAFE_ARCHITECTURE_CONTEXT',
            },
            {
                'resource_type': 'repo_path',
                'resource': '.env',
                'data_class': 'secret',
                'content': 'TOP_SECRET_VALUE_SHOULD_NEVER_CROSS',
            },
        ]
        payload = build_pre_model_payload(
            policy_path=POLICY,
            resources=resources,
            task={'kind': 'code_generation', 'instruction': 'Generate safely'},
        )
        encoded = json.dumps(payload, sort_keys=True)
        self.assertIn('SAFE_ARCHITECTURE_CONTEXT', encoded)
        self.assertNotIn('TOP_SECRET_VALUE_SHOULD_NEVER_CROSS', encoded)
        self.assertFalse(payload['raw_candidates_forwarded'])
        self.assertTrue(payload['production_locked'])
        self.assertEqual(payload['context_manifest']['allowed_count'], 1)
        self.assertEqual(payload['context_manifest']['denied_count'], 1)
        self.assertFalse(payload['context_manifest']['secret_values_recorded'])

    def test_all_denied_context_blocks_invocation(self):
        resources = [{
            'resource_type': 'repo_path',
            'resource': '.env.production',
            'data_class': 'secret',
            'content': 'NEVER_FORWARD_ME',
        }]
        with self.assertRaisesRegex(ContextGovernanceBlocked, 'CONTEXT_GOVERNANCE_BLOCKED'):
            build_pre_model_payload(policy_path=POLICY, resources=resources, task={'kind': 'code_generation'})

    def test_unknown_resource_is_default_denied_and_cannot_leak(self):
        resources = [{
            'resource_type': 'prompt_attachment',
            'resource': 'mystery.bin',
            'data_class': 'internal',
            'content': 'UNKNOWN_PAYLOAD_VALUE',
        }]
        with self.assertRaises(ContextGovernanceBlocked):
            build_pre_model_payload(policy_path=POLICY, resources=resources, task={'kind': 'analysis'})

    def test_empty_context_is_permitted_without_fabricating_resources(self):
        payload = build_pre_model_payload(policy_path=POLICY, resources=[], task={'kind': 'planning'})
        self.assertEqual(payload['context'], [])
        self.assertEqual(payload['context_manifest']['allowed_count'], 0)
        self.assertEqual(payload['context_manifest']['denied_count'], 0)


if __name__ == '__main__':
    unittest.main()
