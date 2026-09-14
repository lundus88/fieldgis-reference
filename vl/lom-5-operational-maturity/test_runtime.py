import unittest
from runtime import ProviderAdapter, validate_adapter, select_provider, evaluate_slo, evidence_freshness, authorize_scheduler_action, recovery_readiness, capacity_guard


def adapter(pid='a', healthy=True, attested=True, caps=frozenset({'analysis'}), credential_mode='oidc'):
    return ProviderAdapter(pid,'1',caps,healthy,credential_mode,attested,'none','disabled')

class LOM5Tests(unittest.TestCase):
    def test_adapter_ready(self):
        self.assertEqual(validate_adapter(adapter())['status'],'READY')
    def test_adapter_requires_attestation(self):
        self.assertEqual(validate_adapter(adapter(attested=False))['reason'],'IDENTITY_ATTESTATION_REQUIRED')
    def test_provider_failover(self):
        result=select_provider([adapter('a',healthy=False),adapter('b'),adapter('c')],'analysis')
        self.assertEqual(result['selected'],'b')
        self.assertEqual(result['fallbacks'],['c'])
    def test_no_provider_holds(self):
        self.assertEqual(select_provider([adapter('a',caps=frozenset({'code'}))],'analysis')['status'],'HOLD')
    def test_slo_pass(self):
        self.assertEqual(evaluate_slo(.999,1000)['status'],'PASS')
    def test_slo_latency_hold(self):
        self.assertEqual(evaluate_slo(.999,6000)['reason'],'LATENCY_SLO_BREACH')
    def test_slo_success_hold(self):
        self.assertEqual(evaluate_slo(.95,1000)['reason'],'SUCCESS_SLO_BREACH')
    def test_evidence_fresh(self):
        self.assertEqual(evidence_freshness(2)['status'],'PASS')
    def test_evidence_stale(self):
        self.assertEqual(evidence_freshness(25)['reason'],'STALE_EVIDENCE')
    def test_scheduler_allows_bounded_read_only(self):
        self.assertEqual(authorize_scheduler_action('REFRESH_EVIDENCE','development',True,True)['decision'],'ALLOW')
    def test_scheduler_blocks_write(self):
        self.assertEqual(authorize_scheduler_action('REFRESH_EVIDENCE','development',False,True)['reason'],'SCHEDULED_WRITE_FORBIDDEN')
    def test_scheduler_escalates_human_only(self):
        self.assertEqual(authorize_scheduler_action('PRODUCTION_RELEASE','development',True,True)['decision'],'HUMAN_REVIEW')
    def test_recovery_ready(self):
        self.assertEqual(recovery_readiness(True,True,True,30)['status'],'READY')
    def test_recovery_requires_restore_drill(self):
        self.assertEqual(recovery_readiness(True,True,False,30)['reason'],'RESTORE_DRILL_EVIDENCE_REQUIRED')
    def test_capacity_allows_nonprod(self):
        self.assertEqual(capacity_guard(5,10,8,'staging')['decision'],'ALLOW')
    def test_capacity_blocks_budget_overrun(self):
        self.assertEqual(capacity_guard(9,10,8,'staging')['reason'],'RESOURCE_BUDGET_EXCEEDED')
    def test_capacity_blocks_production(self):
        self.assertEqual(capacity_guard(1,10,8,'production')['reason'],'PRODUCTION_CAPACITY_FORBIDDEN')

if __name__=='__main__': unittest.main()
