#!/usr/bin/env python3
import unittest
from engine import LeadEvidence,qualify_lead,commercial_handoff

def good(**kw):
    d=dict(
        source_channel="GOOGLE_SEARCH",
        valid_contact_method=True,
        lawful_contact_basis=True,
        source_attribution=True,
        intelligible_need=True,
        service_match=True,
        country_known=True,
        unresolved_fraud_or_abuse=False,
        explicitly_unsupported_market=False,
        prohibited_service=False
    )
    d.update(kw)
    return LeadEvidence(**d)

class DemandEngineTests(unittest.TestCase):
    def test_good_lead_qualifies_without_payment_authority(self):
        r=qualify_lead(good())
        self.assertEqual(r["status"],"QUALIFIED_LEAD")
        self.assertFalse(r["market_support_authority"])
        self.assertFalse(r["payment_authority"])

    def test_unknown_channel_holds(self):
        self.assertEqual(qualify_lead(good(source_channel="RANDOM_BULK_LIST"))["status"],"HOLD")

    def test_no_lawful_contact_basis_needs_qualification(self):
        r=qualify_lead(good(lawful_contact_basis=False))
        self.assertEqual(r["status"],"NEEDS_QUALIFICATION")
        self.assertIn("lawful_contact_basis",r["missing"])

    def test_fraud_signal_holds(self):
        self.assertEqual(qualify_lead(good(unresolved_fraud_or_abuse=True))["reason"],"FRAUD_OR_ABUSE_REVIEW_REQUIRED")

    def test_unsupported_market_holds(self):
        self.assertEqual(qualify_lead(good(explicitly_unsupported_market=True))["reason"],"UNSUPPORTED_MARKET")

    def test_dependencies_block_handoff(self):
        r=commercial_handoff(True,"SUPPORTED",False,False)
        self.assertEqual(r["status"],"CONDITIONAL_HOLD")

    def test_manual_market_review_does_not_become_ready(self):
        r=commercial_handoff(True,"MANUAL_REVIEW",True,True)
        self.assertEqual(r["status"],"MANUAL_REVIEW")

    def test_supported_market_allows_handoff_but_not_payment(self):
        r=commercial_handoff(True,"SUPPORTED",True,True)
        self.assertEqual(r["status"],"READY_FOR_COMMERCIAL_HANDOFF")
        self.assertFalse(r["payment_authority"])
        self.assertEqual(r["production_authority"],"HUMAN_ONLY")

if __name__=="__main__":
    unittest.main()
