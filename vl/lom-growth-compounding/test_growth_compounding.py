import math
import unittest

from growth_compounding import GrowthTelemetry, evaluate_growth_bottleneck


def base(**overrides):
    data = dict(
        objective_id="obj-1",
        project_id="lom",
        evidence_ref="urn:lom:growth:evidence:1",
        evidence_fresh=True,
        time_to_value_minutes=8,
        target_time_to_value_minutes=10,
        cycle_time_minutes=20,
        target_cycle_time_minutes=30,
        automation_eligible_steps=10,
        automated_eligible_steps=10,
        avoidable_human_touches=0,
        qualified_visitors=100,
        activated_users=50,
        target_activation_rate=0.40,
        feedback_to_verified_change_hours=4,
        target_learning_latency_hours=8,
        completed_customers=20,
        repeat_or_referral_customers=8,
        target_repeat_referral_rate=0.30,
        evidence_gap_count=0,
        critical_incident_count=0,
        defect_rate=0.01,
        max_defect_rate=0.02,
        proposed_target="NON_PROD_WORKFLOW",
        reversible=True,
        production=False,
        touches_mandatory_human_boundary=None,
    )
    data.update(overrides)
    return GrowthTelemetry(**data)


class GrowthCompoundingTests(unittest.TestCase):
    def test_healthy_metrics_no_action(self):
        r = evaluate_growth_bottleneck(base())
        self.assertEqual(r["status"], "NO_ACTION")
        self.assertEqual(r["autonomous_ceiling"], "PREPARE_PR")
        self.assertEqual(r["execution_authority"], "NONE")

    def test_speed_bottleneck_selected(self):
        r = evaluate_growth_bottleneck(base(time_to_value_minutes=40))
        self.assertEqual(r["status"], "CANDIDATE")
        self.assertEqual(r["lever"], "SPEED")
        self.assertEqual(r["bottleneck"], "TIME_TO_VALUE")
        self.assertEqual(r["candidate_handoff"], "CAIE")

    def test_quality_dominates_acceleration(self):
        r = evaluate_growth_bottleneck(base(
            time_to_value_minutes=100,
            defect_rate=0.20,
            max_defect_rate=0.02,
        ))
        self.assertEqual(r["status"], "CANDIDATE")
        self.assertEqual(r["reason"], "QUALITY_BOTTLENECK")
        self.assertEqual(r["caie_target"], "EVALUATION")

    def test_automation_never_removes_mandatory_human_gate(self):
        r = evaluate_growth_bottleneck(base(
            automated_eligible_steps=2,
            avoidable_human_touches=5,
            touches_mandatory_human_boundary="PROTECTED_MAIN_MERGE",
        ))
        self.assertEqual(r["status"], "HUMAN_REVIEW")
        self.assertEqual(r["reason"], "MANDATORY_HUMAN_BOUNDARY")

    def test_production_is_human_only(self):
        r = evaluate_growth_bottleneck(base(production=True))
        self.assertEqual(r["status"], "HUMAN_REVIEW")
        self.assertEqual(r["production_authority"], "HUMAN_ONLY")

    def test_stale_or_missing_evidence_fails_closed(self):
        self.assertEqual(
            evaluate_growth_bottleneck(base(evidence_fresh=False))["status"],
            "HOLD",
        )
        self.assertEqual(
            evaluate_growth_bottleneck(base(evidence_ref=""))["status"],
            "HOLD",
        )

    def test_nonfinite_metric_fails_closed(self):
        r = evaluate_growth_bottleneck(base(cycle_time_minutes=math.nan))
        self.assertEqual(r["status"], "HOLD")
        self.assertEqual(r["reason"], "INVALID_NUMERIC_EVIDENCE")

    def test_distribution_candidate_requires_measured_population(self):
        r = evaluate_growth_bottleneck(base(
            qualified_visitors=100,
            activated_users=10,
            target_activation_rate=0.50,
        ))
        self.assertEqual(r["status"], "CANDIDATE")
        self.assertEqual(r["lever"], "DISTRIBUTION")
        self.assertEqual(r["bottleneck"], "ACTIVATION_RATE")

    def test_learning_latency_candidate(self):
        r = evaluate_growth_bottleneck(base(
            feedback_to_verified_change_hours=48,
            target_learning_latency_hours=8,
        ))
        self.assertEqual(r["status"], "CANDIDATE")
        self.assertEqual(r["lever"], "LEARNING")

    def test_compounding_candidate(self):
        r = evaluate_growth_bottleneck(base(
            completed_customers=100,
            repeat_or_referral_customers=5,
            target_repeat_referral_rate=0.30,
        ))
        self.assertEqual(r["status"], "CANDIDATE")
        self.assertEqual(r["lever"], "COMPOUNDING")

    def test_counter_contradictions_fail_closed(self):
        r = evaluate_growth_bottleneck(base(
            automation_eligible_steps=3,
            automated_eligible_steps=4,
        ))
        self.assertEqual(r["status"], "HOLD")
        self.assertEqual(r["reason"], "AUTOMATION_COUNT_CONTRADICTION")

    def test_unknown_or_human_target_does_not_pass(self):
        self.assertEqual(
            evaluate_growth_bottleneck(base(proposed_target="MAGIC"))["status"],
            "HOLD",
        )
        self.assertEqual(
            evaluate_growth_bottleneck(base(proposed_target="FINANCIAL_COMMITMENT"))["status"],
            "HUMAN_REVIEW",
        )


if __name__ == "__main__":
    unittest.main()
