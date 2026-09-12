import unittest
from delegation_policy import authorize_delegation, orchestrate

POLICY_SHA = 'a' * 64
PARENT = {
    'capabilities': ['repo.read', 'branch.write', 'ci.inspect', 'pr.remediate'],
    'resource_scopes': ['repo:lundus88/fieldgis-reference', 'branch:lom-v1'],
    'budget': {
        'max_tokens': 100000,
        'max_cost_microunits': 1000000,
        'max_steps': 50,
        'max_time_seconds': 1800,
        'max_retries': 3,
    },
}


def child(**overrides):
    base = {
        'role': 'implementer',
        'capabilities': ['repo.read', 'branch.write'],
        'resource_scopes': ['repo:lundus88/fieldgis-reference'],
        'budget': {
            'max_tokens': 50000,
            'max_cost_microunits': 500000,
            'max_steps': 25,
            'max_time_seconds': 900,
            'max_retries': 2,
        },
        'context_manifest_required': True,
        'context_policy_sha256': POLICY_SHA,
        'parent_run_id': 'lom-golden-run-001',
    }
    base.update(overrides)
    return base


class DelegationPolicyTests(unittest.TestCase):
    def test_bounded_delegation_allowed(self):
        out = authorize_delegation(PARENT, child())
        self.assertEqual(out['decision'], 'ALLOW')
        self.assertFalse(out['authority_expanded'])

    def test_unknown_capability_expansion_denied(self):
        out = authorize_delegation(PARENT, child(capabilities=['repo.read', 'release.execute']))
        self.assertEqual(out['decision'], 'DENY')
        self.assertEqual(out['reason'], 'CAPABILITY_EXPANSION_BLOCKED')

    def test_scope_expansion_denied(self):
        out = authorize_delegation(PARENT, child(resource_scopes=['repo:other/private']))
        self.assertEqual(out['reason'], 'RESOURCE_SCOPE_EXPANSION_BLOCKED')

    def test_budget_expansion_denied(self):
        budget = dict(child()['budget'])
        budget['max_tokens'] = 200000
        out = authorize_delegation(PARENT, child(budget=budget))
        self.assertEqual(out['reason'], 'BUDGET_EXPANSION_BLOCKED')

    def test_context_policy_digest_required(self):
        out = authorize_delegation(PARENT, child(context_policy_sha256='bad'))
        self.assertEqual(out['reason'], 'CONTEXT_POLICY_DIGEST_REQUIRED')

    def test_parent_run_required(self):
        out = authorize_delegation(PARENT, child(parent_run_id=''))
        self.assertEqual(out['reason'], 'PARENT_RUN_ID_REQUIRED')

    def test_swarm_mode_blocked(self):
        out = orchestrate({
            'workers': [
                {'id': 'builder-1', 'role': 'implementer'},
                {'id': 'cert-1', 'role': 'independent-certifier'},
            ],
            'max_workers': 3,
            'swarm_mode': True,
        })
        self.assertEqual(out['status'], 'BLOCKED')

    def test_controlled_plan_ready(self):
        out = orchestrate({
            'workers': [
                {'id': 'planner-1', 'role': 'planner'},
                {'id': 'builder-1', 'role': 'implementer'},
                {'id': 'qa-1', 'role': 'qa'},
                {'id': 'cert-1', 'role': 'independent-certifier'},
            ],
            'max_workers': 4,
            'swarm_mode': False,
        })
        self.assertEqual(out['status'], 'READY_FOR_CONTROLLED_EXECUTION')
        self.assertEqual(out['production_approval'], 'HUMAN_ONLY')
        self.assertTrue(out['production_locked'])


if __name__ == '__main__':
    unittest.main()
