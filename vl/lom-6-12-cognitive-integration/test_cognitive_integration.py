import unittest
from cognitive_integration import CognitiveInput, evaluate

def base(**kw):
    d=dict(
        objective_id="obj-1", project_id="p-1",
        evidence_status="VERIFIED", evidence_refs=["ev-1"],
        authority_class="CODE_CHANGE", risk="LOW", reversible=True,
        environment="DEVELOPMENT", confidence=0.88,
        options=[
            {"id":"a","expected_value":8,"risk_score":2,"cost_score":2},
            {"id":"b","expected_value":6,"risk_score":1,"cost_score":1},
        ],
        precedent_refs=["decision-12"], blast_radius="LOCAL",
    )
    d.update(kw)
    return CognitiveInput(**d)

class CognitiveIntegrationTests(unittest.TestCase):
    def test_low_risk_reversible_may_prepare_pr_only(self):
        r=evaluate(base())
        self.assertEqual(r["decision"],"PREPARE_PR")
        self.assertEqual(r["execution_authority"],"PREPARE_PR")
        self.assertFalse(r["execution_performed"])
        self.assertEqual(r["protected_main_merge"],"HUMAN_ONLY")

    def test_missing_evidence_holds(self):
        r=evaluate(base(evidence_refs=[]))
        self.assertEqual(r["decision"],"HOLD")

    def test_stale_evidence_holds(self):
        r=evaluate(base(evidence_status="STALE"))
        self.assertEqual(r["decision"],"HOLD")

    def test_production_is_human_only(self):
        r=evaluate(base(environment="PRODUCTION"))
        self.assertEqual(r["decision"],"HOLD")
        self.assertTrue(r["human_decision_required"])

    def test_financial_commitment_is_human_only(self):
        r=evaluate(base(authority_class="FINANCIAL_COMMITMENT"))
        self.assertEqual(r["decision"],"HOLD")
        self.assertEqual(r["next_best_action"],"PREPARE_HUMAN_DECISION_PACKAGE")

    def test_high_risk_requires_human_review(self):
        r=evaluate(base(risk="HIGH"))
        self.assertEqual(r["decision"],"HOLD")
        self.assertTrue(r["human_decision_required"])

    def test_confidence_required(self):
        r=evaluate(base(confidence=None))
        self.assertEqual(r["reason"],"CALIBRATED_CONFIDENCE_REQUIRED")

    def test_options_required(self):
        r=evaluate(base(options=[]))
        self.assertEqual(r["reason"],"DECISION_OPTIONS_REQUIRED")

if __name__ == "__main__":
    unittest.main()
