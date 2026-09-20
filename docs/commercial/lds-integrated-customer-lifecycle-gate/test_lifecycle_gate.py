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

    def test_advisory_never_advances_hard_gate(self):
        self.assertFalse(advisory_can_advance_hard_gate())

if __name__=="__main__": unittest.main()
