#!/usr/bin/env python3
import unittest
from gate import CountryEvidence,classify_country,order_authority,global_status

def base(**kw):
    d=dict(
      country_code="ZZ",currency_supported=True,tax_known=True,
      contract_jurisdiction_known=True,privacy_known=True,data_residency_known=True,
      payment_supported=True,support_timezone_supported=True,builder_capability_supported=True,
      delivery_uat_supported=True,invoice_export_known=True,restrictions_cleared=True,
      evidence_current=True,human_approved=True,explicitly_prohibited=False
    )
    d.update(kw)
    return CountryEvidence(**d)

class GlobalCommerceTests(unittest.TestCase):
    def test_supported_requires_all_gates(self):
        self.assertEqual(classify_country(base())["classification"],"SUPPORTED")

    def test_unknown_tax_is_manual_review(self):
        r=classify_country(base(tax_known=False))
        self.assertEqual(r["classification"],"MANUAL_REVIEW")
        self.assertIn("tax_treatment",r["missing"])

    def test_unsupported_payment_is_manual_review(self):
        self.assertEqual(classify_country(base(payment_supported=False))["classification"],"MANUAL_REVIEW")

    def test_stale_evidence_is_manual_review(self):
        self.assertEqual(classify_country(base(evidence_current=False))["classification"],"MANUAL_REVIEW")

    def test_human_approval_required(self):
        self.assertEqual(classify_country(base(human_approved=False))["reason"],"HUMAN_APPROVAL_REQUIRED")

    def test_explicit_prohibition_is_not_supported(self):
        self.assertEqual(classify_country(base(explicitly_prohibited=True))["classification"],"NOT_SUPPORTED")

    def test_global_enquiry_separate_from_checkout(self):
        r=order_authority("SUPPORTED",False)
        self.assertTrue(r["enquiry_allowed"])
        self.assertEqual(r["decision"],"QUOTE_ONLY_NO_AUTOMATIC_CHECKOUT")

    def test_manual_review_never_auto_charges(self):
        self.assertEqual(order_authority("MANUAL_REVIEW",True)["decision"],"MANUAL_REVIEW_ONLY")

    def test_global_summary_not_ready_with_mixed_states(self):
        r=global_status({"AA":"SUPPORTED","BB":"MANUAL_REVIEW"})
        self.assertFalse(r["global_paid_order_ready"])

if __name__=="__main__":
    unittest.main()
