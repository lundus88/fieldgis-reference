import unittest
from delegation_policy import authorize_delegation, orchestrate


PARENT={
  'capabilities':['repo.read','branch.write','ci.inspect','pr.remediate'],
  'resource_scopes':['repo:lundus88/fieldgis-reference','branch:feature'],
  'budget':{'max_tokens':100000,'max_cost_microunits':1000000,'max_steps':50},
}


def child(**overrides):
    base={
      'role':'implementer',
      'capabilities':['repo.read','branch.write'],
      'resource_scopes':['repo:lundus88/fieldgis-reference'],
      'budget':{'max_tokens':50000,'max_cost_microunits':500000,'max_steps':25},
      'context_manifest_required':True,
    }
    base.update(overrides)
    return base


class DelegationPolicyTests(unittest.TestCase):
    def test_bounded_delegation_allowed(self):
        out=authorize_delegation(PARENT,child())
        self.assertEqual(out['decision'],'ALLOW')
        self.assertFalse(out['authority_expanded'])
        self.assertEqual(out['production_approval'],'HUMAN_ONLY')

    def test_capability_expansion_denied(self):
        out=authorize_delegation(PARENT,child(capabilities=['repo.read','production.approve']))
        self.assertEqual(out['decision'],'DENY')

    def test_resource_scope_expansion_denied(self):
        out=authorize_delegation(PARENT,child(resource_scopes=['repo:other/private']))
        self.assertEqual(out['reason'],'RESOURCE_SCOPE_EXPANSION_BLOCKED')

    def test_budget_expansion_denied(self):
        out=authorize_delegation(PARENT,child(budget={'max_tokens':200000,'max_cost_microunits':500000,'max_steps':25}))
        self.assertEqual(out['reason'],'BUDGET_EXPANSION_BLOCKED')

    def test_governed_context_required(self):
        out=authorize_delegation(PARENT,child(context_manifest_required=False))
        self.assertEqual(out['reason'],'GOVERNED_CONTEXT_REQUIRED')

    def test_swarm_mode_forbidden_by_default(self):
        out=orchestrate({'workers':[],'max_workers':3,'swarm_mode':True,'independent_certifier_separate':True})
        self.assertEqual(out['status'],'BLOCKED')
        self.assertEqual(out['reason'],'SWARM_MODE_FORBIDDEN_BY_DEFAULT')

    def test_independent_certifier_must_remain_separate(self):
        out=orchestrate({'workers':['planner','implementer'],'max_workers':3,'swarm_mode':False,'independent_certifier_separate':False})
        self.assertEqual(out['reason'],'INDEPENDENT_CERTIFIER_REQUIRED')

    def test_controlled_plan_ready_with_human_production_approval(self):
        out=orchestrate({'workers':['planner','implementer','qa'],'max_workers':3,'swarm_mode':False,'independent_certifier_separate':True})
        self.assertEqual(out['status'],'READY_FOR_CONTROLLED_EXECUTION')
        self.assertEqual(out['production_approval'],'HUMAN_ONLY')
        self.assertTrue(out['production_locked'])


if __name__=='__main__':
    unittest.main()
