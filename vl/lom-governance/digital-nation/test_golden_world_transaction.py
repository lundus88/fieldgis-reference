import unittest

from golden_world_transaction import preview_summary, validate_golden_world_transaction


def _event(n, event_type, **extra):
    base = {
        "event_id": f"evt_{n}",
        "event_type": event_type,
        "occurred_at": f"2026-09-29T08:{n:02d}:00Z",
        "actor_id": "member_001",
        "subject_id": "member_001",
        "source_system": "preview-fixture",
        "correlation_id": "journey_001",
        "evidence_ref": f"evidence://fixture/{n}",
        "policy_version": "draft-v1",
        "authority_context": {"decision": "ALLOW", "claims": []},
    }
    base.update(extra)
    return base


def _valid():
    return [
        _event(1, "member.registered"),
        _event(2, "member.identity_verified", assurance_level="P0"),
        _event(3, "skill.signal_verified", skill_id="skill_001", verification_method="fixture"),
        _event(4, "opportunity.matched", opportunity_id="opp_001", match_basis="fixture"),
        _event(5, "offer.accepted", offer_id="offer_001", terms_ref="terms://fixture/1"),
        _event(6, "order.created", order_id="order_001", buyer_id="buyer_001", seller_id="member_001", offer_id="offer_001", amount=100, currency="MYR"),
        _event(
            7,
            "payment.confirmed",
            order_id="order_001",
            payment_reference_id="pay_001",
            provider="sandbox-fixture",
            amount=100,
            currency="MYR",
            evidence_source="sandbox_signed_callback_fixture",
        ),
        _event(8, "delivery.submitted", order_id="order_001", delivery_id="delivery_001", seller_id="member_001"),
        _event(9, "delivery.accepted", order_id="order_001", acceptance_id="accept_001", buyer_id="buyer_001"),
        _event(
            10,
            "earning.recorded",
            order_id="order_001",
            earning_id="earn_001",
            beneficiary_id="member_001",
            gross_amount=100,
            fees=10,
            net_amount=90,
            currency="MYR",
        ),
        _event(11, "reputation.updated", member_id="member_001", reputation_event_id="rep_001", reason_code="DELIVERY_ACCEPTED"),
        _event(12, "referral.attributed", order_id="order_001", referrer_id="member_002", attribution_rule="fixture-v1"),
    ]


class GoldenWorldTransactionTests(unittest.TestCase):
    def test_valid_golden_world_transaction_allows(self):
        result = validate_golden_world_transaction(_valid())
        self.assertEqual(result.decision, "ALLOW")
        self.assertEqual(result.reasons, [])

    def test_payment_user_assertion_fails_closed(self):
        events = _valid()
        events[6]["evidence_source"] = "user_assertion"
        result = validate_golden_world_transaction(events)
        self.assertEqual(result.decision, "DENY")
        self.assertTrue(any("INVALID_PAYMENT_EVIDENCE_SOURCE" in r for r in result.reasons))

    def test_earning_before_acceptance_fails_closed(self):
        events = _valid()
        earning = events.pop(9)
        events.insert(8, earning)
        result = validate_golden_world_transaction(events)
        self.assertEqual(result.decision, "DENY")
        self.assertIn("EARNING_BEFORE_ACCEPTANCE", result.reasons)

    def test_prohibited_sovereign_claim_fails_closed(self):
        events = _valid()
        events[0]["authority_context"]["claims"] = ["government_authority"]
        result = validate_golden_world_transaction(events)
        self.assertEqual(result.decision, "DENY")
        self.assertTrue(any("PROHIBITED_AUTHORITY_CLAIM" in r for r in result.reasons))

    def test_consequential_event_requires_authority(self):
        events = _valid()
        events[9]["authority_context"]["decision"] = "AUTO_UNBOUNDED"
        result = validate_golden_world_transaction(events)
        self.assertEqual(result.decision, "DENY")
        self.assertTrue(any("CONSEQUENTIAL_AUTHORITY_NOT_APPROVED" in r for r in result.reasons))

    def test_preview_summary_never_grants_production_execution(self):
        summary = preview_summary(_valid())
        self.assertEqual(summary["decision"], "ALLOW")
        self.assertEqual(summary["mode"], "PREVIEW_SYNTHETIC_ONLY")
        self.assertFalse(summary["production_authority"])
        self.assertFalse(summary["payment_execution"])
        self.assertFalse(summary["payout_execution"])


if __name__ == "__main__":
    unittest.main()
