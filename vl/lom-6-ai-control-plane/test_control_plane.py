import unittest
from control_plane import AgentRecord, AgentMetrics, validate_agent, score_agent, roi_summary, recommend_agent, agent_health, authorize_control_plane_action


def agent(aid='a', status='active', caps=frozenset({'analysis'})):
    return AgentRecord(aid, '1', 'worker', caps, 'lom', status)


def metrics(success=.999, correctness=.98, safety=.999, latency=1200, cost=.20, value=2.0):
    return AgentMetrics(success, correctness, safety, latency, cost, value)


class LOM6Tests(unittest.TestCase):
    def test_agent_registry_ready(self):
        self.assertEqual(validate_agent(agent())['status'], 'READY')

    def test_agent_registry_requires_capabilities(self):
        self.assertEqual(validate_agent(agent(caps=frozenset()))['reason'], 'CAPABILITIES_REQUIRED')

    def test_score_agent_pass(self):
        self.assertEqual(score_agent(metrics())['status'], 'PASS')

    def test_score_agent_review_on_safety(self):
        self.assertEqual(score_agent(metrics(safety=.95))['status'], 'REVIEW')

    def test_invalid_metrics_hold(self):
        self.assertEqual(score_agent(metrics(success=1.1))['reason'], 'INVALID_METRICS')

    def test_roi_positive(self):
        result = roi_summary(100, 20, 300, 500, 50)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['gross_value'], 850.0)
        self.assertEqual(result['net_value'], 830.0)

    def test_roi_zero_cost(self):
        self.assertIsNone(roi_summary(5, 0, 10, 0)['roi_pct'])

    def test_recommend_agent_by_score(self):
        records = [agent('a'), agent('b')]
        scores = {'a': metrics(cost=.4, value=1.0), 'b': metrics(cost=.1, value=2.0)}
        self.assertEqual(recommend_agent(records, scores, 'analysis')['selected_agent'], 'b')

    def test_recommend_agent_has_fallback(self):
        result = recommend_agent([agent('a'), agent('b')], {'a': metrics(), 'b': metrics(latency=1800)}, 'analysis')
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(len(result['fallbacks']), 1)

    def test_recommend_agent_requires_capability(self):
        result = recommend_agent([agent('a', caps=frozenset({'code'}))], {'a': metrics()}, 'analysis')
        self.assertEqual(result['status'], 'HOLD')

    def test_health_holds_stale_evidence(self):
        self.assertEqual(agent_health(agent(), metrics(), False)['health'], 'HOLD')

    def test_health_escalates_safety(self):
        self.assertEqual(agent_health(agent(), metrics(safety=.95), True)['health'], 'HUMAN_REVIEW')

    def test_health_auto_prepare_on_weak_performance(self):
        weak = metrics(success=.70, correctness=.70, safety=.995, latency=15000, cost=5, value=.1)
        self.assertEqual(agent_health(agent(), weak, True)['health'], 'AUTO_PREPARE')

    def test_health_monitors_good_agent(self):
        self.assertEqual(agent_health(agent(), metrics(), True)['health'], 'MONITOR')

    def test_human_only_action_escalates(self):
        self.assertEqual(authorize_control_plane_action('PRODUCTION_RELEASE', 'development')['decision'], 'HUMAN_REVIEW')

    def test_authority_change_escalates(self):
        self.assertEqual(authorize_control_plane_action('EVALUATE_AGENT', 'development', True)['decision'], 'HUMAN_REVIEW')

    def test_production_action_holds(self):
        self.assertEqual(authorize_control_plane_action('EVALUATE_AGENT', 'production')['decision'], 'HOLD')

    def test_nonproduction_bounded_action_allowed(self):
        self.assertEqual(authorize_control_plane_action('EVALUATE_AGENT', 'staging')['decision'], 'ALLOW')


if __name__ == '__main__':
    unittest.main()
