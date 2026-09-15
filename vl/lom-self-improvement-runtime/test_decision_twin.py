import unittest

from decision_twin import (
    CandidateSpec,
    EvaluationPolicy,
    HistoricalReplay,
    evaluate_counterfactual,
    execute_candidate,
)


def replay(run_id, project_id="ebkl", **overrides):
    data = dict(
        run_id=run_id,
        project_id=project_id,
        evidence_sha=f"sha-{run_id}",
        source_reference=f"evidence://{run_id}",
        evidence_state="VERIFIED",
        evidence_fresh=True,
        baseline_success=True,
        candidate_success=True,
        baseline_hold=False,
        candidate_hold=False,
        baseline_correctness=0.80,
        candidate_correctness=0.90,
        baseline_safety=0.95,
        candidate_safety=0.96,
        baseline_evidence_quality=0.80,
        candidate_evidence_quality=0.90,
        baseline_latency_ms=1000,
        candidate_latency_ms=980,
        baseline_cost=1.0,
        candidate_cost=1.02,
        authority_expansion_incidents=0,
        fabricated_pass_incidents=0,
        autonomous_production_incidents=0,
    )
    data.update(overrides)
    return HistoricalReplay(**data)


def candidate(**overrides):
    data = dict(
        candidate_id="route-v2",
        target="ROUTING",
        proposed_change="Prefer model B for bounded code-analysis tasks.",
        risk="LOW",
        reversible=True,
        production=False,
    )
    data.update(overrides)
    return CandidateSpec(**data)


class DecisionTwinTests(unittest.TestCase):
    def good_rows(self):
        return [
            replay("r1", "ebkl"),
            replay("r2", "ebkl"),
            replay("r3", "lunduslead"),
            replay("r4", "lunduslead"),
            replay("r5", "sabahlot"),
        ]

    def test_safe_improvement_becomes_sandbox_candidate(self):
        result = evaluate_counterfactual(candidate(), self.good_rows())
        self.assertEqual(result["status"], "SANDBOX_CANDIDATE")
        self.assertEqual(result["next_stage"], "LOM_6_7_VALIDATION_SANDBOX")
        self.assertEqual(result["execution_authority"], "NONE")
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["production_authority"], "HUMAN_ONLY")

    def test_missing_evidence_fails_closed(self):
        rows = self.good_rows()
        rows[0] = replay("r1", evidence_sha=None)
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "REPLAY_EVIDENCE_INVALID")

    def test_stale_evidence_fails_closed(self):
        rows = self.good_rows()
        rows[0] = replay("r1", evidence_fresh=False)
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["status"], "HOLD")

    def test_duplicate_run_id_fails_closed(self):
        rows = self.good_rows()
        rows[-1] = replay("r1", "sabahlot")
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["reason"], "DUPLICATE_RUN_ID")

    def test_insufficient_sample_holds(self):
        result = evaluate_counterfactual(
            candidate(), self.good_rows()[:2],
            policy=EvaluationPolicy(minimum_runs=3, minimum_projects=2),
        )
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "INSUFFICIENT_HISTORICAL_RUNS")

    def test_insufficient_project_diversity_holds(self):
        rows = [replay(f"r{i}", "ebkl") for i in range(1, 6)]
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "INSUFFICIENT_PROJECT_DIVERSITY")

    def test_safety_regression_rejects(self):
        rows = self.good_rows()
        rows[2] = replay("r3", "lunduslead", candidate_safety=0.90)
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["status"], "REJECT")
        self.assertEqual(result["reason"], "SAFETY_REGRESSION")

    def test_authority_expansion_incident_rejects(self):
        rows = self.good_rows()
        rows[0] = replay("r1", authority_expansion_incidents=1)
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["status"], "REJECT")
        self.assertEqual(result["reason"], "AUTHORITY_EXPANSION_INCIDENT")

    def test_fabricated_pass_incident_rejects(self):
        rows = self.good_rows()
        rows[0] = replay("r1", fabricated_pass_incidents=1)
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["reason"], "FABRICATED_PASS_INCIDENT")

    def test_autonomous_production_incident_rejects(self):
        rows = self.good_rows()
        rows[0] = replay("r1", autonomous_production_incidents=1)
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["reason"], "AUTONOMOUS_PRODUCTION_INCIDENT")

    def test_cost_regression_rejects(self):
        rows = [replay(f"r{i}", "ebkl" if i < 4 else "lunduslead", candidate_cost=1.25) for i in range(1, 6)]
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["reason"], "COST_BUDGET_REGRESSION")

    def test_latency_regression_rejects(self):
        rows = [replay(f"r{i}", "ebkl" if i < 4 else "lunduslead", candidate_latency_ms=1200) for i in range(1, 6)]
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["reason"], "LATENCY_BUDGET_REGRESSION")

    def test_hold_rate_regression_rejects(self):
        rows = self.good_rows()
        rows[0] = replay("r1", candidate_hold=True)
        result = evaluate_counterfactual(candidate(), rows)
        self.assertEqual(result["reason"], "HOLD_RATE_REGRESSION")

    def test_production_candidate_requires_human(self):
        result = evaluate_counterfactual(candidate(production=True), self.good_rows())
        self.assertEqual(result["status"], "HUMAN_REVIEW")

    def test_human_only_target_requires_human(self):
        result = evaluate_counterfactual(candidate(target="PRODUCTION_RELEASE"), self.good_rows())
        self.assertEqual(result["status"], "HUMAN_REVIEW")

    def test_irreversible_candidate_holds(self):
        result = evaluate_counterfactual(candidate(reversible=False), self.good_rows())
        self.assertEqual(result["status"], "HOLD")

    def test_fingerprint_is_order_independent(self):
        rows = self.good_rows()
        a = evaluate_counterfactual(candidate(), rows)
        b = evaluate_counterfactual(candidate(), list(reversed(rows)))
        self.assertEqual(a["decision_twin_fingerprint"], b["decision_twin_fingerprint"])

    def test_execution_is_forbidden(self):
        with self.assertRaises(PermissionError):
            execute_candidate()


if __name__ == "__main__":
    unittest.main()
