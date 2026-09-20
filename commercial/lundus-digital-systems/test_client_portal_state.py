#!/usr/bin/env python3
import unittest
from client_portal_state import *

def base(**kw):
    d=dict(
      customer_authorized=True,project_state="BUILDING",project_evidence_current=True,
      quote_status="approved",invoice_status="issued",payment_status="paid",payment_verified=True,
      receipt_issued=True,milestone_funded=True,build_status="SUCCEEDED",
      qa_status="passed",qa_evidence=True,uat_status="pending",uat_evidence=False,
      delivery_status="pending",delivery_evidence=False,production_deployed_evidence=False
    )
    d.update(kw)
    return PortalEvidence(**d)

class PortalTests(unittest.TestCase):
    def test_unauthorized_customer_denied(self):
        self.assertEqual(compose(base(customer_authorized=False))["portal_status"],"DENY")
    def test_stale_evidence_reviews(self):
        self.assertEqual(compose(base(project_evidence_current=False))["portal_status"],"REVIEW")
    def test_paid_requires_provider_evidence(self):
        r=compose(base(payment_verified=False))
        self.assertEqual(r["commercial"]["payment"],"REVIEW")
        self.assertEqual(r["delivery"]["milestone"],"NOT_FUNDED")
    def test_qa_pass_requires_evidence(self):
        self.assertEqual(compose(base(qa_evidence=False))["delivery"]["qa"],"REVIEW")
    def test_uat_acceptance_requires_evidence(self):
        self.assertEqual(compose(base(uat_status="accepted",uat_evidence=False))["delivery"]["uat"],"REVIEW")
    def test_delivery_requires_evidence(self):
        self.assertEqual(compose(base(delivery_status="delivered",delivery_evidence=False))["delivery"]["delivery"],"REVIEW")
    def test_factory_success_not_production(self):
        self.assertEqual(compose(base())["delivery"]["production"],"NOT_PROVEN")
    def test_portal_cannot_mutate(self):
        self.assertFalse(can_mutate_state())

if __name__=="__main__":
    unittest.main()
