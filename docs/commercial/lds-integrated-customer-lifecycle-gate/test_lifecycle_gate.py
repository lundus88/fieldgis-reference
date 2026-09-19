#!/usr/bin/env python3
import unittest
from lifecycle_gate import *

def good(**kw):
    d=dict(
      approved_scope=True,human_approved_quotation=True,payment_reconciled=True,
      kickoff_ready=True,human_kickoff_approved=True,build_complete=True,
      qa_evidence=True,customer_acceptance_evidence=True,delivery_evidence=True,
      material_scope_change=False,change_request_approved=False,stale_or_contradictory=False
    )
    d.update(kw); return LifecycleEvidence(**d)

class LifecycleGateTests(unittest.TestCase):
    def test_payment_alone_cannot_start_build(self):
        e=good(kickoff_ready=False,human_kickoff_approved=False,build_complete=False)
        self.assertEqual(evaluate(e)["reason"],"KICKOFF_GATE_REQUIRED")
    def test_material_change_requires_change_request(self):
        e=good(material_scope_change=True,change_request_approved=False)
        self.assertEqual(evaluate(e)["reason"],"APPROVED_CHANGE_REQUEST_REQUIRED")
    def test_qa_requires_evidence(self):
        self.assertEqual(evaluate(good(qa_evidence=False))["next_stage"],"QA")
    def test_uat_requires_customer_evidence(self):
        self.assertEqual(evaluate(good(customer_acceptance_evidence=False))["next_stage"],"UAT")
    def test_delivery_requires_evidence(self):
        self.assertEqual(evaluate(good(delivery_evidence=False))["next_stage"],"DELIVERY")
    def test_stale_hard_gate_holds(self):
        self.assertEqual(evaluate(good(stale_or_contradictory=True))["status"],"HOLD")
    def test_complete_flow_does_not_grant_production(self):
        r=evaluate(good())
        self.assertEqual(r["status"],"DELIVERY_COMPLETE")
        self.assertEqual(r["production_authority"],"HUMAN_ONLY")
        self.assertFalse(r["source_truth_mutated"])
    def test_advisory_never_advances_hard_gate(self):
        self.assertFalse(advisory_can_advance_hard_gate())

if __name__=="__main__": unittest.main()
