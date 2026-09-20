#!/usr/bin/env python3
import unittest
from intent_compiler import *
from exception_autopilot import *
from completion_gate import *
from automation_extensions import *

class ValueAddTests(unittest.TestCase):
    def test_intent_compiles_only_confirmed_scope(self):
        i=IntentPackage("Generate leads","LD_LAUNCH",1,True,True,["Lead form"],["Lead form submits"],[],[],[])
        r=compile_work_package(i)
        self.assertTrue(r["executable"])
        self.assertEqual(len(r["work_package_digest"]),64)
        self.assertFalse(r["production_authority"])

    def test_intent_with_open_questions_holds(self):
        i=IntentPackage("Build portal","LD_SYSTEM",1,True,True,["Login"],["Login works"],[],[],["Which SSO?"])
        self.assertEqual(compile_work_package(i)["status"],"HUMAN_GATE")

    def test_exception_autopilot_uses_bounded_playbook(self):
        r=decide(ExceptionEvidence("BUILD_TEST_FAILURE",0,3,1.0,10.0,True))
        self.assertEqual(r["playbook"],"REPAIR_AND_RETEST")

    def test_exception_security_opens_breaker(self):
        r=decide(ExceptionEvidence("BUILD_TEST_FAILURE",0,3,1.0,10.0,True,security_signal=True))
        self.assertTrue(r["circuit_breaker"])

    def test_completion_requires_real_evidence(self):
        e=CompletionEvidence("QA_PASSED",["core"],["core"],[],True,True)
        self.assertEqual(evaluate_completion(e)["reason"],"COMPLETION_EVIDENCE_INCOMPLETE")

    def test_completion_pass_never_uses_self_assertion(self):
        e=CompletionEvidence("QA_PASSED",["core"],["core"],["test-run-1"],True,True)
        r=evaluate_completion(e)
        self.assertTrue(r["completion_authorized"])
        self.assertFalse(r["agent_self_assertion_sufficient"])

    def test_customer_dependency_auto_followup(self):
        r=customer_dependency_action(DependencyState(["logo"],True,True))
        self.assertEqual(r["status"],"AUTO_NOTIFY")

    def test_deadline_risk_reprioritises_when_allowed(self):
        r=deadline_guardian(DeadlineState(4,5,1,False,True))
        self.assertEqual(r["reason"],"DEADLINE_RISK_REPRIORITISE_WITHIN_POLICY")

    def test_router_respects_quality_before_cost(self):
        cs=[
          RouteCandidate("cheap-low",True,True,0.6,0.99,1.0,0.9),
          RouteCandidate("good",True,True,0.9,0.95,3.0,0.8)
        ]
        r=route_execution(cs,0.8,0.9)
        self.assertEqual(r["route_id"],"good")

    def test_learning_cannot_silently_mutate_policy(self):
        r=learning_candidate(LearningEvidence(True,True,True,True,True))
        self.assertEqual(r["status"],"CANDIDATE_UPDATE")
        self.assertFalse(r["policy_mutation_allowed"])

    def test_commercial_recovery_cannot_charge(self):
        r=commercial_recovery(CommercialRecoveryState("PAYMENT_FAILED",True,True,0,3))
        self.assertFalse(r["charge_authority"])

    def test_change_impact_routes_to_existing_flow(self):
        r=change_impact_analysis(ChangeImpact(True,True,True,True,True,True,True))
        self.assertEqual(r["status"],"READY_FOR_EXISTING_CHANGE_REQUEST_FLOW")
        self.assertFalse(r["approval_authority"])

    def test_circuit_breaker_fails_closed(self):
        r=circuit_breaker(CircuitSignals(cost_spike=True))
        self.assertEqual(r["status"],"OPEN")
        self.assertFalse(r["autonomous_actions_allowed"])

if __name__=="__main__":
    unittest.main()
