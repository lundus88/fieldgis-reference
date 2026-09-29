import unittest

from dispute_adapter import next_step, open_dispute
from education_skill_adapter import normalize_skill_signal, to_world_event
from reputation_adapter import summarize, validate_reputation_event


class EducationSkillAdapterTests(unittest.TestCase):
    def test_self_report_cannot_be_verified(self):
        out = normalize_skill_signal({
            "member_id": "m1",
            "skill_id": "s1",
            "status": "VERIFIED",
            "verification_method": "SELF_REPORT",
            "evidence_ref": "e1",
        })
        self.assertEqual(out["decision"], "DENY")

    def test_verified_assessment_emits_world_event(self):
        out = to_world_event({
            "member_id": "m1",
            "skill_id": "s1",
            "status": "VERIFIED",
            "verification_method": "ASSESSMENT",
            "evidence_ref": "evidence://assessment/1",
        }, "journey_1")
        self.assertEqual(out["decision"], "ALLOW")
        self.assertEqual(out["event_type"], "skill.signal_verified")
        self.assertFalse(out["production_authority"])


class ReputationAdapterTests(unittest.TestCase):
    def test_reputation_requires_evidence(self):
        out = validate_reputation_event({
            "member_id": "m1",
            "dimension": "DELIVERY_RELIABILITY",
            "reason_code": "ACCEPTED",
            "source_event_id": "evt1",
        })
        self.assertEqual(out["decision"], "DENY")

    def test_global_score_is_forbidden(self):
        out = validate_reputation_event({
            "member_id": "m1",
            "dimension": "DELIVERY_RELIABILITY",
            "reason_code": "ACCEPTED",
            "evidence_ref": "e1",
            "source_event_id": "evt1",
            "global_score": 99,
        })
        self.assertEqual(out["decision"], "DENY")

    def test_summary_is_dimensional_only(self):
        out = summarize([{
            "member_id": "m1",
            "dimension": "VERIFIED_SKILL",
            "reason_code": "ASSESSMENT_PASS",
            "evidence_ref": "e1",
            "source_event_id": "evt1",
        }])
        self.assertEqual(out["accepted_events"], 1)
        self.assertIsNone(out["single_global_score"])


class DisputeAdapterTests(unittest.TestCase):
    def test_open_dispute_does_not_assume_misconduct(self):
        out = open_dispute({
            "dispute_id": "d1",
            "order_id": "o1",
            "opened_by": "m1",
            "reason_code": "NON_RECEIPT",
            "evidence_ref": "e1",
        })
        self.assertEqual(out["decision"], "ALLOW")
        self.assertFalse(out["misconduct_determined"])
        self.assertFalse(out["court_judgment"])

    def test_high_impact_routes_to_human_review(self):
        out = next_step({
            "state": "EVIDENCE_GATHERING",
            "reason_code": "HIGH_VALUE_PAYMENT",
            "evidence_complete": True,
        })
        self.assertEqual(out["next_state"], "HUMAN_REVIEW")

    def test_resolution_requires_human_decision(self):
        out = next_step({
            "state": "HUMAN_REVIEW",
            "reason_code": "HIGH_VALUE_PAYMENT",
        })
        self.assertEqual(out["decision"], "HOLD")
        self.assertEqual(out["reason"], "HUMAN_DECISION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
