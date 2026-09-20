#!/usr/bin/env python3
import unittest
from engine import DiscoveryContext,should_ask,next_question,evaluate,build_brief,recommend_offer

def complete(**kw):
    d=dict(
        objective="Generate qualified enquiries",
        solution_type="WEBSITE",
        target_users=["prospective customers"],
        must_have=["service pages","lead capture"],
        existing_assets=["domain"],
        integrations=[],
        data_sensitivity="PUBLIC_ONLY",
        delivery_constraints=["phased launch"]
    )
    d.update(kw)
    return DiscoveryContext(**d)

class DiscoveryEngineTests(unittest.TestCase):
    def test_material_question_only(self):
        self.assertTrue(should_ask({"scope"},False))
        self.assertFalse(should_ask({"cosmetic_preference"},False))
        self.assertFalse(should_ask({"scope"},True))

    def test_progressive_questioning_starts_with_objective(self):
        q=next_question(DiscoveryContext())
        self.assertEqual(q["id"],"objective")

    def test_known_information_is_not_reasked(self):
        c=DiscoveryContext(objective="Generate leads",solution_type="WEBSITE",target_users=["buyers"],must_have=["lead form"],existing_assets=["domain"],data_sensitivity="PUBLIC_ONLY",delivery_constraints=["budget band"])
        self.assertIsNone(next_question(c)["id"])

    def test_automation_asks_about_integrations(self):
        c=DiscoveryContext(objective="Automate quotations",solution_type="AUTOMATION",target_users=["staff"],must_have=["generate quote"],existing_assets=["CRM"])
        self.assertEqual(next_question(c)["id"],"integrations")

    def test_complete_context_ready_for_confirmation_not_quote(self):
        r=evaluate(complete())
        self.assertEqual(r["status"],"READY_FOR_CUSTOMER_CONFIRMATION")
        self.assertFalse(r["authoritative_quotation"])
        self.assertFalse(r["payment_authority"])

    def test_bypass_request_forces_human_review(self):
        r=evaluate(complete(bypass_request=True))
        self.assertEqual(r["status"],"NEEDS_HUMAN_REVIEW")

    def test_contradiction_forces_human_review(self):
        r=evaluate(complete(contradictions=["must be public and must be private"]))
        self.assertEqual(r["reason"],"MATERIAL_REQUIREMENT_CONTRADICTION")

    def test_material_unverified_integration_forces_review(self):
        r=evaluate(complete(integrations=["legacy ERP"],integration_feasibility_unverified=True))
        self.assertEqual(r["status"],"NEEDS_HUMAN_REVIEW")

    def test_offer_mapping(self):
        self.assertEqual(recommend_offer("AI_AUTOMATION"),"LD_AI")
        self.assertEqual(recommend_offer("UNKNOWN"),"LD_DISCOVERY")

    def test_brief_is_unconfirmed_and_non_authoritative(self):
        b=build_brief(complete())
        self.assertEqual(b["customer_confirmation_state"],"UNCONFIRMED")
        self.assertFalse(b["authoritative_quotation"])

if __name__=="__main__":
    unittest.main()
