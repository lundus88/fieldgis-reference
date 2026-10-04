#!/usr/bin/env python3
import unittest
from gate import CountryEvidence,InternationalOperatingEvidence,classify_country,order_authority,global_status,assess_international_readiness

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


class InternationalReadinessTests(unittest.TestCase):
    def operating(self, **kw):
        d=dict(
          home_country_code="MY",
          locale_language_ready=True,
          multi_currency_ready=True,
          timezone_normalization_ready=True,
          jurisdiction_knowledge_ready=True,
          cross_border_payment_ready=True,
          accounting_invoice_ready=True,
          privacy_security_ready=True,
          support_delivery_ready=True,
          observability_recovery_ready=True,
          evidence_current=True,
          real_cross_border_paid_transaction_verified=False,
          delivery_acceptance_verified=False,
          accounting_receipt_verified=False,
          transaction_country_code=None,
          human_validated_international_claim=False,
        )
        d.update(kw)
        return InternationalOperatingEvidence(**d)

    def test_no_foreign_supported_market_holds(self):
        r=assess_international_readiness({"MY":"SUPPORTED"},self.operating())
        self.assertEqual(r["status"],"HOLD")
        self.assertEqual(r["reason"],"NO_FOREIGN_MARKET_SUPPORTED")

    def test_operating_gap_holds(self):
        r=assess_international_readiness(
          {"MY":"SUPPORTED","SG":"SUPPORTED"},
          self.operating(multi_currency_ready=False)
        )
        self.assertEqual(r["status"],"HOLD")
        self.assertIn("multi_currency",r["missing"])

    def test_complete_operating_evidence_without_real_transaction_is_candidate_only(self):
        r=assess_international_readiness(
          {"MY":"SUPPORTED","SG":"SUPPORTED"},
          self.operating()
        )
        self.assertEqual(r["status"],"INTERNATIONAL_CANDIDATE")
        self.assertFalse(r["public_international_claim_allowed"])
        self.assertFalse(r["worldwide_claim_allowed"])

    def test_transaction_must_bind_to_supported_foreign_market(self):
        r=assess_international_readiness(
          {"MY":"SUPPORTED","SG":"SUPPORTED","US":"MANUAL_REVIEW"},
          self.operating(
            real_cross_border_paid_transaction_verified=True,
            delivery_acceptance_verified=True,
            accounting_receipt_verified=True,
            transaction_country_code="US",
          )
        )
        self.assertEqual(r["status"],"INTERNATIONAL_CANDIDATE")
        self.assertFalse(r["public_international_claim_allowed"])

    def test_real_cross_border_proof_still_requires_human_claim_validation(self):
        r=assess_international_readiness(
          {"MY":"SUPPORTED","SG":"SUPPORTED"},
          self.operating(
            real_cross_border_paid_transaction_verified=True,
            delivery_acceptance_verified=True,
            accounting_receipt_verified=True,
            transaction_country_code="SG",
          )
        )
        self.assertEqual(r["status"],"HUMAN_GATE")
        self.assertEqual(r["reason"],"HUMAN_VALIDATION_REQUIRED_FOR_INTERNATIONAL_CLAIM")

    def test_validated_international_status_requires_full_evidence_and_human_validation(self):
        r=assess_international_readiness(
          {"MY":"SUPPORTED","SG":"SUPPORTED"},
          self.operating(
            real_cross_border_paid_transaction_verified=True,
            delivery_acceptance_verified=True,
            accounting_receipt_verified=True,
            transaction_country_code="SG",
            human_validated_international_claim=True,
          )
        )
        self.assertEqual(r["status"],"INTERNATIONAL_VALIDATED")
        self.assertTrue(r["public_international_claim_allowed"])
        self.assertFalse(r["worldwide_claim_allowed"])
        self.assertEqual(r["production_authority"],"HUMAN_ONLY")
        self.assertEqual(r["self_approval"],"FORBIDDEN")

    def test_worldwide_claim_is_never_inferred_from_one_foreign_market(self):
        r=assess_international_readiness(
          {"MY":"SUPPORTED","SG":"SUPPORTED"},
          self.operating(
            real_cross_border_paid_transaction_verified=True,
            delivery_acceptance_verified=True,
            accounting_receipt_verified=True,
            transaction_country_code="SG",
            human_validated_international_claim=True,
          )
        )
        self.assertFalse(r["worldwide_claim_allowed"])

if __name__=="__main__":
    unittest.main()
