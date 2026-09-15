import unittest

from mission_control import (
    ControlIntent,
    MissionInput,
    OperationalTelemetry,
    build_mission_control_view,
    build_snapshot,
    classify_telemetry,
    evaluate_control_intent,
)


def mission(**overrides):
    data = dict(
        objective_id="obj-1",
        lifecycle_state="VALIDATE",
        evidence_status="COMPLETE",
        risk_state="LOW",
        agent_states=(("VALIDATOR", "READY"),),
    )
    data.update(overrides)
    return MissionInput(**data)


def telemetry(**overrides):
    data = dict(
        objective_id="obj-1",
        project_id="ebkl",
        golden_workflow_id="golden-5",
        source_reference="ci://ebkl/run/1",
        evidence_fresh=True,
        evidence_gap_count=0,
        incident_count=0,
        critical_incident_count=0,
        pending_approvals=0,
        estimated_cost_usd=1.25,
        cost_budget_usd=5.0,
        elapsed_ms=1200,
        time_budget_ms=5000,
        retry_count=0,
        retry_budget=2,
        slo_breached=False,
    )
    data.update(overrides)
    return OperationalTelemetry(**data)


def control(**overrides):
    data = dict(
        objective_id="obj-1",
        action="PAUSE",
        environment="NON_PRODUCTION",
        requested_by="director",
        evidence_status="COMPLETE",
        source_reference="evidence://control/1",
        evidence_fresh=True,
        reversible=True,
    )
    data.update(overrides)
    return ControlIntent(**data)


class MissionControlV2Tests(unittest.TestCase):
    def test_v1_snapshot_contract_remains_compatible(self):
        snapshot = build_snapshot(mission())
        self.assertEqual(snapshot["objective_id"], "obj-1")
        self.assertEqual(snapshot["recommended_director_action"], "NONE")
        self.assertNotIn("schema_version", snapshot)

    def test_clean_telemetry_monitors(self):
        self.assertEqual(classify_telemetry(telemetry())["action_class"], "MONITOR")

    def test_stale_telemetry_holds(self):
        result = classify_telemetry(telemetry(evidence_fresh=False))
        self.assertEqual(result, {"action_class": "HOLD", "reason": "TELEMETRY_EVIDENCE_STALE"})

    def test_missing_provenance_holds(self):
        self.assertEqual(
            classify_telemetry(telemetry(source_reference=None))["reason"],
            "TELEMETRY_PROVENANCE_REQUIRED",
        )

    def test_evidence_gap_holds(self):
        self.assertEqual(classify_telemetry(telemetry(evidence_gap_count=1))["reason"], "EVIDENCE_GAPS_PRESENT")

    def test_cost_budget_overrun_holds(self):
        self.assertEqual(
            classify_telemetry(telemetry(estimated_cost_usd=6.0, cost_budget_usd=5.0))["reason"],
            "COST_BUDGET_EXCEEDED",
        )

    def test_time_budget_overrun_holds(self):
        self.assertEqual(
            classify_telemetry(telemetry(elapsed_ms=6000, time_budget_ms=5000))["reason"],
            "TIME_BUDGET_EXCEEDED",
        )

    def test_retry_budget_overrun_holds(self):
        self.assertEqual(
            classify_telemetry(telemetry(retry_count=3, retry_budget=2))["reason"],
            "RETRY_BUDGET_EXCEEDED",
        )

    def test_critical_incident_requires_human_review(self):
        result = classify_telemetry(telemetry(incident_count=1, critical_incident_count=1))
        self.assertEqual(result["action_class"], "HUMAN_REVIEW")
        self.assertEqual(result["reason"], "CRITICAL_INCIDENT_PRESENT")

    def test_pending_approval_requires_human_review(self):
        self.assertEqual(
            classify_telemetry(telemetry(pending_approvals=1))["reason"],
            "HUMAN_APPROVAL_PENDING",
        )

    def test_slo_breach_requires_human_review(self):
        self.assertEqual(classify_telemetry(telemetry(slo_breached=True))["reason"], "SLO_BREACH")

    def test_nonprod_pause_is_prepare_only(self):
        result = evaluate_control_intent(control())
        self.assertEqual(result["status"], "PREPARE_CONTROL")
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["execution_authority"], "NONE")

    def test_nonprod_quarantine_is_prepare_only(self):
        result = evaluate_control_intent(control(action="QUARANTINE"))
        self.assertEqual(result["status"], "PREPARE_CONTROL")
        self.assertFalse(result["execution_performed"])

    def test_stop_always_requires_human_decision(self):
        result = evaluate_control_intent(control(action="STOP"))
        self.assertEqual(result["status"], "HUMAN_REVIEW")
        self.assertEqual(result["reason"], "STOP_REQUIRES_HUMAN_DECISION")

    def test_production_control_is_human_only(self):
        result = evaluate_control_intent(control(environment="PRODUCTION"))
        self.assertEqual(result["status"], "HUMAN_REVIEW")
        self.assertEqual(result["reason"], "PRODUCTION_CONTROL_HUMAN_ONLY")
        self.assertEqual(result["production_authority"], "HUMAN_ONLY")

    def test_irreversible_control_requires_human(self):
        result = evaluate_control_intent(control(reversible=False))
        self.assertEqual(result["status"], "HUMAN_REVIEW")

    def test_incomplete_control_evidence_holds(self):
        result = evaluate_control_intent(control(evidence_status="PARTIAL"))
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "CONTROL_EVIDENCE_INCOMPLETE")

    def test_portfolio_view_exposes_governance_boundaries(self):
        view = build_mission_control_view([mission()], [telemetry()], [control()])
        self.assertEqual(view["schema_version"], 2)
        self.assertEqual(view["mode"], "READ_ONLY_NON_PRODUCTION")
        self.assertEqual(view["autonomous_ceiling"], "PREPARE_PR")
        self.assertEqual(view["production_authority"], "HUMAN_ONLY")
        self.assertEqual(view["protected_main_merge"], "HUMAN_ONLY")
        self.assertEqual(view["control_execution"], "DISABLED")

    def test_portfolio_aggregates_operational_metrics(self):
        view = build_mission_control_view(
            [mission()],
            [
                telemetry(project_id="ebkl", estimated_cost_usd=1.25),
                telemetry(project_id="sabahlot", objective_id="obj-2", estimated_cost_usd=2.75),
            ],
        )
        self.assertEqual(view["portfolio"]["telemetry_record_count"], 2)
        self.assertEqual(view["portfolio"]["estimated_cost_total_usd"], 4.0)
        self.assertEqual(view["portfolio"]["evidence_gap_total"], 0)

    def test_hold_precedes_human_review_in_overall_view(self):
        view = build_mission_control_view(
            [mission()],
            [
                telemetry(project_id="ebkl", evidence_gap_count=1),
                telemetry(project_id="sabahlot", objective_id="obj-2", pending_approvals=1),
            ],
        )
        self.assertEqual(view["overall_action_class"], "HOLD")


if __name__ == "__main__":
    unittest.main()
