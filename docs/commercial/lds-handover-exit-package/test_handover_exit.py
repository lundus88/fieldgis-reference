#!/usr/bin/env python3
import unittest
from handover_exit import *

def e(**kw):
    d=dict(
      ownership_terms_clear=True,deliverables_complete=True,export_evidence=True,
      third_party_obligations_disclosed=True,secure_credential_transfer_ready=True,
      access_revocation_plan_ready=True,customer_acceptance=True,unresolved_issue=False
    )
    d.update(kw); return HandoverEvidence(**d)

class HandoverTests(unittest.TestCase):
    def test_missing_export_blocks(self):
        self.assertEqual(assess(e(export_evidence=False))["status"],"HOLD")
    def test_customer_acceptance_required(self):
        self.assertEqual(assess(e(customer_acceptance=False))["status"],"CUSTOMER_ACCEPTANCE_REQUIRED")
    def test_unresolved_issue_reviews(self):
        self.assertEqual(assess(e(unresolved_issue=True))["status"],"REVIEW")
    def test_close_requires_revocation_evidence(self):
        self.assertEqual(close_handover(True,False,True)["decision"],"HOLD")
    def test_close_requires_manifest(self):
        self.assertEqual(close_handover(True,True,False)["decision"],"HOLD")
    def test_plaintext_secret_forbidden(self):
        self.assertFalse(plaintext_secret_allowed())

if __name__=="__main__": unittest.main()
