import unittest

from engine import (
    FundingAllocation, WorkerProfile, Task, QAResult,
    qa_decision, transition_task, create_payable_entitlement,
    reputation_delta, evaluate_scale_gate,
)

def passing_qa():
    return QAResult(
        qa_result_id="qa-1",
        factual_consistency=30,
        hook_quality=13,
        clarity_readability=13,
        message_focus=9,
        cta_quality=9,
        duration_format=5,
        tone_audience_fit=5,
        policy_safety=10,
        confidence=0.95,
    )

class TestEconomicParticipation(unittest.TestCase):
    def setUp(self):
        self.fund = FundingAllocation("fund-1", approved_minor=10000, reserved_minor=5000)
        self.worker = WorkerProfile("worker-1")
        self.task = Task("task-1", funding_id="fund-1", worker_fee_minor=500)

    def happy_to_qa(self):
        self.assertEqual(transition_task(self.task,"FUND_CONFIRMED","FINANCE",funding=self.fund)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"MARK_READY","SYSTEM",funding=self.fund)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"ASSIGN_WORKER","SYSTEM",worker=self.worker)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"START_TASK","WORKER",worker=self.worker)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"SUBMIT_WORK","WORKER",worker=self.worker)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"START_QA","QA_SERVICE")["decision"],"ALLOW")

    def test_happy_path_to_payable_entitlement(self):
        self.happy_to_qa()
        qa = passing_qa()
        self.assertEqual(transition_task(self.task,"QA_PASS","QA_SERVICE",qa=qa)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"CREATE_PAYABLE","FINANCE",funding=self.fund)["decision"],"ALLOW")
        e = create_payable_entitlement(self.task,self.fund)
        self.assertEqual(e.status,"ELIGIBLE_FOR_HUMAN_PAYOUT_REVIEW")
        self.assertEqual(e.amount_minor,500)

    def test_unfunded_task_cannot_start_paid_flow(self):
        bad = FundingAllocation("fund-1",approved_minor=100,reserved_minor=100)
        r=transition_task(self.task,"FUND_CONFIRMED","FINANCE",funding=bad)
        self.assertEqual(r["decision"],"DENY")
        self.assertEqual(self.task.status,"DRAFT")

    def test_actor_cannot_bypass_state_machine(self):
        r=transition_task(self.task,"ASSIGN_WORKER","WORKER",worker=self.worker)
        self.assertEqual(r["decision"],"DENY")
        self.assertEqual(self.task.status,"DRAFT")

    def test_hard_fail_never_passes_even_high_score(self):
        qa=QAResult("qa-x",30,15,15,10,10,5,5,10,0.99,("FAKE_TESTIMONIAL",))
        self.assertEqual(qa_decision(qa)["decision"],"REJECT")

    def test_low_confidence_escalates(self):
        qa=QAResult("qa-x",30,15,15,10,10,5,5,10,0.50,())
        self.assertEqual(qa_decision(qa)["decision"],"ESCALATE")

    def test_revision_limit(self):
        self.happy_to_qa()
        rev=QAResult("qa-r1",30,10,10,7,6,4,4,9,0.90,())
        self.assertEqual(qa_decision(rev)["decision"],"REVISION")
        self.assertEqual(transition_task(self.task,"QA_REVISION","QA_SERVICE",qa=rev)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"START_REVISION","WORKER",worker=self.worker)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"SUBMIT_WORK","WORKER",worker=self.worker)["decision"],"ALLOW")
        self.assertEqual(transition_task(self.task,"START_QA","QA_SERVICE")["decision"],"ALLOW")
        rev2=QAResult("qa-r2",30,10,10,7,6,4,4,9,0.90,())
        self.assertEqual(transition_task(self.task,"QA_REVISION","QA_SERVICE",qa=rev2)["decision"],"ALLOW")
        r=transition_task(self.task,"START_REVISION","WORKER",worker=self.worker)
        self.assertEqual(r["decision"],"DENY")
        self.assertEqual(r["reason"],"REVISION_LIMIT_REACHED")

    def test_provider_cannot_claim_paid_without_success(self):
        self.happy_to_qa()
        qa=passing_qa()
        transition_task(self.task,"QA_PASS","QA_SERVICE",qa=qa)
        transition_task(self.task,"CREATE_PAYABLE","FINANCE",funding=self.fund)
        transition_task(self.task,"PROCESS_PAYOUT","FINANCE")
        r=transition_task(self.task,"CONFIRM_PAID","PAYMENT_ADAPTER",provider_success=False)
        self.assertEqual(r["decision"],"DENY")

    def test_reconciliation_required(self):
        self.happy_to_qa()
        qa=passing_qa()
        transition_task(self.task,"QA_PASS","QA_SERVICE",qa=qa)
        transition_task(self.task,"CREATE_PAYABLE","FINANCE",funding=self.fund)
        transition_task(self.task,"PROCESS_PAYOUT","FINANCE")
        transition_task(self.task,"CONFIRM_PAID","PAYMENT_ADAPTER",provider_success=True)
        r=transition_task(self.task,"RECONCILE","FINANCE",reconciliation_ok=False)
        self.assertEqual(r["decision"],"DENY")
        self.assertEqual(self.task.status,"PAID")

    def test_reputation_is_bounded(self):
        self.assertEqual(reputation_delta(accepted=True,revision_count=0,integrity_event=False,on_time=True),5)
        self.assertLess(reputation_delta(accepted=False,revision_count=2,integrity_event=True,on_time=False),0)

    def test_shadow_scale_gate(self):
        metrics={
            "first_pass_rate":0.82,
            "final_pass_rate":0.98,
            "serious_fact_errors":0,
            "revision_rate":0.18,
            "median_minutes":8,
            "human_intervention_rate":0.15,
            "duplicate_entitlements":0,
            "unfunded_entitlements":0,
            "unauthorized_transitions":0,
            "synthetic_only":True,
        }
        r=evaluate_scale_gate(metrics)
        self.assertEqual(r["decision"],"READY_FOR_HUMAN_GO_NO_GO")
        self.assertEqual(r["live_pilot_authority"],"HUMAN_ONLY")

    def test_synthetic_mislabel_is_hard_stop(self):
        metrics={
            "first_pass_rate":1.0,
            "final_pass_rate":1.0,
            "serious_fact_errors":0,
            "revision_rate":0.0,
            "median_minutes":1,
            "human_intervention_rate":0.0,
            "duplicate_entitlements":0,
            "unfunded_entitlements":0,
            "unauthorized_transitions":0,
            "synthetic_only":False,
        }
        self.assertEqual(evaluate_scale_gate(metrics)["decision"],"NO_GO")

if __name__ == "__main__":
    unittest.main()
