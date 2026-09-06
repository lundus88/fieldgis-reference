import json
import unittest
from pathlib import Path

from route_model import ModelRoutingBlocked, route_model


HERE = Path(__file__).resolve().parent
REGISTRY = json.loads((HERE / 'model-registry.json').read_text())


def request(**overrides):
    base = {
        'task_class': 'analysis',
        'data_class': 'source_code',
        'input_tokens': 12000,
        'output_tokens': 4000,
        'cost_ceiling': 50.0,
        'autonomy_horizon': 1,
        'max_retention': '30_days',
    }
    base.update(overrides)
    return base


class ModelRoutingTests(unittest.TestCase):
    def test_sensitive_task_rejects_retention_incompatible_model(self):
        evidence = route_model(REGISTRY, request(data_class='customer_private', max_retention='none'))
        rejected = {x['model_id']: x['reasons'] for x in evidence['rejected']}
        self.assertIn('sandbox-provider-b/model-retained-v1', rejected)
        self.assertIn('privacy', rejected['sandbox-provider-b/model-retained-v1'])
        self.assertNotEqual(evidence['selected_model_id'], 'sandbox-provider-b/model-retained-v1')

    def test_deprecated_model_is_never_selected_or_fallback(self):
        evidence = route_model(REGISTRY, request())
        self.assertNotEqual(evidence['selected_model_id'], 'sandbox-provider-a/model-legacy-v0')
        self.assertNotIn('sandbox-provider-a/model-legacy-v0', evidence['fallback_chain'])
        rejected = {x['model_id']: x['reasons'] for x in evidence['rejected']}
        self.assertIn('status:deprecated', rejected['sandbox-provider-a/model-legacy-v0'])

    def test_fallback_chain_contains_only_policy_approved_candidates(self):
        evidence = route_model(REGISTRY, request(task_class='security_review', max_retention='none'))
        self.assertEqual(evidence['selected_model_id'], 'sandbox-provider-b/model-deep-v2')
        self.assertEqual(evidence['fallback_chain'], [])

    def test_same_policy_inputs_are_deterministic_and_auditable(self):
        req = request(task_class='code_generation', max_retention='none')
        first = route_model(REGISTRY, req)
        second = route_model(REGISTRY, req)
        self.assertEqual(first, second)
        self.assertTrue(first['deterministic'])
        self.assertEqual(len(first['request_sha256']), 64)
        self.assertEqual(len(first['decision_sha256']), 64)

    def test_cost_ceiling_blocks_when_no_model_is_affordable(self):
        with self.assertRaisesRegex(ModelRoutingBlocked, 'MODEL_ROUTING_BLOCKED'):
            route_model(REGISTRY, request(cost_ceiling=0.001, max_retention='none'))

    def test_token_ceiling_blocks_oversized_request(self):
        with self.assertRaises(ModelRoutingBlocked):
            route_model(REGISTRY, request(input_tokens=999999, max_retention='none'))

    def test_autonomy_horizon_is_policy_bounded(self):
        evidence = route_model(REGISTRY, request(autonomy_horizon=3, max_retention='none'))
        self.assertEqual(evidence['selected_model_id'], 'sandbox-provider-b/model-deep-v2')
        with self.assertRaises(ModelRoutingBlocked):
            route_model(REGISTRY, request(autonomy_horizon=99, max_retention='none'))

    def test_unavailable_registry_entry_fails_over_only_to_approved_alternative(self):
        registry = json.loads(json.dumps(REGISTRY))
        for model in registry['models']:
            if model['id'] == 'sandbox-provider-a/model-fast-v1':
                model['status'] = 'unavailable'
        evidence = route_model(registry, request(task_class='code_generation', max_retention='none'))
        self.assertEqual(evidence['selected_model_id'], 'sandbox-provider-b/model-deep-v2')
        self.assertNotIn('sandbox-provider-a/model-fast-v1', evidence['fallback_chain'])


if __name__ == '__main__':
    unittest.main()
