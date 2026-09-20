import unittest
from runtime import Adapter, WorkItem, InteropResourceRuntime

class LOM45Tests(unittest.TestCase):
    def setUp(self):
        self.rt = InteropResourceRuntime()
        self.a = Adapter('a','provider-a','active',('analysis','planning'),'none','disabled',0.90,500,0.5)
        self.b = Adapter('b','provider-b','active',('analysis',),'none','disabled',0.95,900,0.8)

    def item(self, **kw):
        base = dict(work_id='w1', capability='analysis', input_tokens=1000, output_tokens=1000,
                    max_cost=10.0, max_latency_ms=2000, min_quality=0.8, priority=10, tenant='t1')
        base.update(kw)
        return WorkItem(**base)

    def test_provider_neutral_route_selects_best_score(self):
        r = self.rt.route([self.a,self.b], self.item())
        self.assertEqual(r['decision'],'ROUTE')
        self.assertEqual(r['adapter_id'],'b')

    def test_failover_chain_present(self):
        r = self.rt.route([self.a,self.b], self.item())
        self.assertIn('a', r['fallback_chain'])

    def test_inactive_adapter_rejected(self):
        bad = Adapter('x','p','inactive',('analysis',),'none','disabled',1.0,1,0.0)
        r = self.rt.route([bad], self.item())
        self.assertEqual(r['decision'],'HOLD')

    def test_sensitive_data_requires_zero_retention(self):
        retained = Adapter('x','p','active',('analysis',),'30_days','disabled',1.0,1,0.0)
        r = self.rt.route([retained], self.item(data_class='secret'))
        self.assertEqual(r['reason'],'NO_COMPATIBLE_ADAPTER')

    def test_human_only_target_escalates(self):
        r = self.rt.route([self.a], self.item(capability='PRODUCTION_RELEASE'))
        self.assertEqual(r['decision'],'HUMAN_REVIEW')

    def test_cost_ceiling_holds_when_none_fit(self):
        r = self.rt.route([self.a], self.item(max_cost=0.01))
        self.assertEqual(r['decision'],'HOLD')

    def test_quality_floor_enforced(self):
        r = self.rt.route([self.a], self.item(min_quality=0.99))
        self.assertEqual(r['decision'],'HOLD')

    def test_latency_ceiling_enforced(self):
        r = self.rt.route([self.a], self.item(max_latency_ms=100))
        self.assertEqual(r['decision'],'HOLD')

    def test_global_budget_allows_bounded_request(self):
        b = dict(tokens=100,cost_microunits=100,steps=10,time_seconds=60,retries=2)
        q = dict(tokens=50,cost_microunits=50,steps=5,time_seconds=30,retries=1)
        self.assertEqual(self.rt.enforce_budget(b,q)['decision'],'ALLOW')

    def test_global_budget_blocks_expansion(self):
        b = dict(tokens=100,cost_microunits=100,steps=10,time_seconds=60,retries=2)
        q = dict(tokens=101,cost_microunits=50,steps=5,time_seconds=30,retries=1)
        self.assertEqual(self.rt.enforce_budget(b,q)['reason'],'BUDGET_EXPANSION_BLOCKED')

    def test_queue_fairness_gives_distinct_tenants_first(self):
        i1=self.item(work_id='1',tenant='a',priority=10)
        i2=self.item(work_id='2',tenant='a',priority=9)
        i3=self.item(work_id='3',tenant='b',priority=8)
        out=self.rt.schedule([i1,i2,i3],2)
        self.assertEqual({x.tenant for x in out},{'a','b'})

    def test_capacity_plan_only_certified_nonprod(self):
        pools=[
            {'pool_id':'prod','status':'certified','environment':'production','ambient_production_credentials':False,'cpu_available':8,'memory_mb_available':16000,'estimated_hourly_cost':1},
            {'pool_id':'dev','status':'certified','environment':'development','ambient_production_credentials':False,'cpu_available':8,'memory_mb_available':16000,'estimated_hourly_cost':2},
        ]
        r=self.rt.capacity_plan(pools,2,1024)
        self.assertEqual(r['pool_id'],'dev')

    def test_no_safe_capacity_holds(self):
        pools=[{'pool_id':'x','status':'uncertified','environment':'development','ambient_production_credentials':False,'cpu_available':8,'memory_mb_available':16000}]
        self.assertEqual(self.rt.capacity_plan(pools,2,1024)['decision'],'HOLD')

    def test_autonomous_ceiling_is_prepare_pr(self):
        self.assertEqual(self.rt.autonomous_ceiling(),'PREPARE_PR')

    def test_production_capacity_allocation_forbidden(self):
        with self.assertRaisesRegex(PermissionError,'HUMAN_APPROVAL_REQUIRED'):
            self.rt.allocate_production_capacity()

    def test_resource_mode_reserves_capacity_before_exhaustion(self):
        self.assertEqual(self.rt.resource_mode(70,100)['decision'],'SHED_NON_CRITICAL')
        self.assertEqual(self.rt.resource_mode(85,100)['decision'],'CONTROLLED_MODE')
        self.assertEqual(self.rt.resource_mode(95,100)['decision'],'CRITICAL_ONLY')

    def test_internal_experiment_shed_first(self):
        r=self.rt.admission_control('INTERNAL_EXPERIMENT','SHED_NON_CRITICAL')
        self.assertEqual(r['decision'],'QUEUE')

    def test_critical_only_preserves_p0_p1(self):
        self.assertEqual(self.rt.admission_control('P0','CRITICAL_ONLY')['decision'],'ALLOW')
        self.assertEqual(self.rt.admission_control('P3','CRITICAL_ONLY')['decision'],'QUEUE')

    def test_checkpoint_requires_evidence(self):
        r=self.rt.checkpoint('w1',3,[],[],'continue')
        self.assertEqual(r['decision'],'HOLD')

    def test_resume_never_restarts_from_zero(self):
        cp=self.rt.checkpoint('w1',3,['artifact-1'],[],'run-tests')
        r=self.rt.resume_plan(cp,['provider-b'])
        self.assertEqual(r['decision'],'RESUME')
        self.assertFalse(r['restart_from_zero'])
        self.assertEqual(r['resume_step'],3)

    def test_resource_exhaustion_prefers_fallback(self):
        r=self.rt.handle_resource_exhaustion(True,['provider-b'])
        self.assertEqual(r['decision'],'FALLBACK_ROUTE')

    def test_resource_exhaustion_without_checkpoint_holds(self):
        r=self.rt.handle_resource_exhaustion(False,['provider-b'])
        self.assertEqual(r['decision'],'HOLD')

if __name__ == '__main__':
    unittest.main()
