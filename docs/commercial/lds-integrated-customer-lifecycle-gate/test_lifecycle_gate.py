#!/usr/bin/env python3
import unittest
from lifecycle_gate import *

def req(fr,to,evidence=(),deps=None,human=True,key="k1",org="o1",authority_org="o1",**kw):
    return TransitionRequest(
      org_id=org,
      from_state=fr,
      to_state=to,
      evidence=frozenset(evidence),
      dependencies=deps or {},
      authority=AuthorityReceipt(authority_org,"actor-1","2026-09-20T10:00:00Z",human,tuple(sorted(evidence)),key),
      **kw
    )

class ControlPlaneTests(unittest.TestCase):
    def test_illegal_edge_holds(self):
        r=evaluate_transition(req("VISITOR","BUILDING",["legitimate_lead_evidence"]))
        self.assertEqual(r["reason"],"ILLEGAL_STATE_TRANSITION")

    def test_dependency_not_ready_holds(self):
        r=evaluate_transition(req(
          "ASSESSMENT","QUALIFIED",
          ["assessment_complete","market_supported"],
          {"workflow_assessment":True,"global_commerce_readiness":False},
          human=False
        ))
        self.assertEqual(r["reason"],"DEPENDENCY_NOT_READY")

    def test_missing_evidence_holds(self):
        r=evaluate_transition(req(
          "BLUEPRINT_APPROVED","QUOTATION_APPROVED",
          ["pricing_reviewed"],
          {"pricing_estimation_intelligence":True,"commercial_document_system":True}
        ))
        self.assertEqual(r["reason"],"REQUIRED_EVIDENCE_MISSING")

    def test_human_authority_required(self):
        r=evaluate_transition(req(
          "BLUEPRINT_APPROVED","QUOTATION_APPROVED",
          ["pricing_reviewed","human_approved_quotation"],
          {"pricing_estimation_intelligence":True,"commercial_document_system":True},
          human=False
        ))
        self.assertEqual(r["reason"],"EXPLICIT_HUMAN_AUTHORITY_REQUIRED")

    def test_valid_transition_produces_receipt_without_mutating_truth(self):
        r=evaluate_transition(req(
          "BLUEPRINT_APPROVED","QUOTATION_APPROVED",
          ["pricing_reviewed","human_approved_quotation"],
          {"pricing_estimation_intelligence":True,"commercial_document_system":True}
        ))
        self.assertEqual(r["status"],"PASS")
        self.assertTrue(r["transition_authorized"])
        self.assertEqual(len(r["receipt_digest"]),64)
        self.assertFalse(r["source_truth_mutated"])

    def test_replay_is_idempotent(self):
        r=evaluate_transition(req("VISITOR","ASSESSMENT",["legitimate_lead_evidence"],human=False,key="same"),frozenset({"same"}))
        self.assertEqual(r["status"],"IDEMPOTENT_REPLAY")
        self.assertFalse(r["transition_authorized"])

    def test_cross_org_authority_denied(self):
        r=evaluate_transition(req("VISITOR","ASSESSMENT",["legitimate_lead_evidence"],human=False,authority_org="o2"))
        self.assertEqual(r["reason"],"CROSS_ORGANIZATION_AUTHORITY_DENIED")

    def test_material_change_requires_change_request(self):
        r=evaluate_transition(req(
          "KICKOFF_APPROVED","BUILDING",["scope_snapshot_current"],human=False,
          material_scope_change=True,change_request_approved=False
        ))
        self.assertEqual(r["reason"],"APPROVED_CHANGE_REQUEST_REQUIRED")

    def test_standard_paid_order_can_auto_kickoff(self):
        r=evaluate_transition(req(
          "PAYMENT_RECONCILED","KICKOFF_APPROVED",
          ["kickoff_ready","autonomous_kickoff_eligibility"],
          {"customer_onboarding":True,"autonomous_operations":True},
          human=False
        ))
        self.assertEqual(r["status"],"PASS")
        self.assertTrue(r["transition_authorized"])

    def test_kickoff_without_auto_or_human_receipt_holds(self):
        r=evaluate_transition(req(
          "PAYMENT_RECONCILED","KICKOFF_APPROVED",
          ["kickoff_ready"],
          {"customer_onboarding":True,"autonomous_operations":True},
          human=False
        ))
        self.assertEqual(r["reason"],"ANY_OF_REQUIRED_EVIDENCE_MISSING")

    def test_exception_kickoff_accepts_real_human_approval(self):
        r=evaluate_transition(req(
          "PAYMENT_RECONCILED","KICKOFF_APPROVED",
          ["kickoff_ready","human_kickoff_approval"],
          {"customer_onboarding":True,"autonomous_operations":True},
          human=True
        ))
        self.assertEqual(r["status"],"PASS")

    def test_fake_human_kickoff_receipt_is_rejected(self):
        r=evaluate_transition(req(
          "PAYMENT_RECONCILED","KICKOFF_APPROVED",
          ["kickoff_ready","human_kickoff_approval"],
          {"customer_onboarding":True,"autonomous_operations":True},
          human=False
        ))
        self.assertEqual(r["reason"],"EXPLICIT_HUMAN_AUTHORITY_REQUIRED")

    def test_compatibility_gate_accepts_autonomous_kickoff(self):
        e=LifecycleEvidence(
          approved_scope=True,human_approved_quotation=True,payment_reconciled=True,
          kickoff_ready=True,human_kickoff_approved=False,build_complete=False,
          qa_evidence=False,customer_acceptance_evidence=False,delivery_evidence=False,
          autonomous_kickoff_eligible=True
        )
        r=evaluate(e)
        self.assertEqual(r["reason"],"BUILD_IN_PROGRESS")

    def test_advisory_never_advances_hard_gate(self):
        self.assertFalse(advisory_can_advance_hard_gate())

if __name__=="__main__": unittest.main()
