import unittest

from mission_control import ControlIntent, MissionInput, OperationalTelemetry, build_mission_control_view
from truth_bound_mission_control import (
    TRUTH_SOURCE,
    build_truth_bound_mission_control_view,
    validate_project_truth_snapshot,
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
        source_reference="ci://ebkl/run/1",
        evidence_fresh=True,
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
    )
    data.update(overrides)
    return ControlIntent(**data)


def truth(status="VERIFIED", reason="EVIDENCE_BOUND_STATE", **overrides):
    data = {
        "schema": "lom.project-state-truth/1",
        "mode": "READ_ONLY_NON_PRODUCTION",
        "overall": "MONITOR",
        "projects": [
            {
                "project_id": "ebkl",
                "status": status,
                "reason": reason,
            }
        ],
        "snapshot_fingerprint": "abc123",
        "autonomous_ceiling": "PREPARE_PR",
        "protected_main_merge": "HUMAN_ONLY",
        "production_authority": "HUMAN_ONLY",
        "execution_authority": "NONE",
        "execution_performed": False,
    }
    data.update(overrides)
    return data


class TruthBoundMissionControlTests(unittest.TestCase):
    def test_existing_v2_contract_is_unchanged(self):
        view = build_mission_control_view([mission()], [telemetry()])
        self.assertEqual(view["schema_version"], 2)
        self.assertNotIn("project_truth", view)
        self.assertNotIn("project_status_authority", view)

    def test_missing_truth_fails_closed(self):
        view = build_truth_bound_mission_control_view([mission()], [telemetry()])
        self.assertEqual(view["schema_version"], 3)
        self.assertEqual(view["overall_action_class"], "HOLD")
        self.assertEqual(view["project_truth"]["reason"], "PROJECT_TRUTH_REQUIRED")

    def test_verified_project_binds_and_monitors(self):
        view = build_truth_bound_mission_control_view([mission()], [telemetry()], project_truth_snapshot=truth())
        self.assertEqual(view["overall_action_class"], "MONITOR")
        self.assertEqual(view["project_status_authority"], TRUTH_SOURCE)
        self.assertEqual(view["telemetry"][0]["canonical_project_state"], "VERIFIED")
        self.assertEqual(view["telemetry"][0]["effective_action_class"], "MONITOR")
        self.assertEqual(view["project_truth"]["snapshot_fingerprint"], "abc123")

    def test_unverified_project_holds(self):
        view = build_truth_bound_mission_control_view(
            [mission()], [telemetry()], project_truth_snapshot=truth(status="UNVERIFIED")
        )
        self.assertEqual(view["overall_action_class"], "HOLD")
        self.assertEqual(view["telemetry"][0]["effective_action_class"], "HOLD")

    def test_truth_hold_project_holds(self):
        view = build_truth_bound_mission_control_view(
            [mission()], [telemetry()], project_truth_snapshot=truth(status="HOLD", reason="STALE_EVIDENCE")
        )
        self.assertEqual(view["overall_action_class"], "HOLD")
        self.assertEqual(view["telemetry"][0]["canonical_project_reason"], "STALE_EVIDENCE")

    def test_failed_project_holds_dashboard(self):
        view = build_truth_bound_mission_control_view(
            [mission()], [telemetry()], project_truth_snapshot=truth(status="FAILED", reason="FAIL_EVIDENCE_PRESENT")
        )
        self.assertEqual(view["overall_action_class"], "HOLD")
        self.assertEqual(view["portfolio"]["truth_blocked_project_count"], 1)

    def test_missing_project_in_truth_holds(self):
        snapshot = truth(projects=[])
        view = build_truth_bound_mission_control_view([mission()], [telemetry()], project_truth_snapshot=snapshot)
        self.assertEqual(view["overall_action_class"], "HOLD")
        self.assertEqual(view["portfolio"]["truth_missing_project_count"], 1)
        self.assertEqual(view["telemetry"][0]["canonical_project_reason"], "PROJECT_TRUTH_MISSING_FOR_PROJECT")

    def test_wrong_schema_holds(self):
        result = validate_project_truth_snapshot(truth(schema="wrong"))
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "PROJECT_TRUTH_SCHEMA_INVALID")

    def test_weakened_production_authority_holds(self):
        result = validate_project_truth_snapshot(truth(production_authority="AUTO"))
        self.assertEqual(result["reason"], "PROJECT_TRUTH_AUTHORITY_MISMATCH")

    def test_execution_performed_true_holds(self):
        result = validate_project_truth_snapshot(truth(execution_performed=True))
        self.assertEqual(result["reason"], "PROJECT_TRUTH_EXECUTION_STATE_INVALID")

    def test_duplicate_project_truth_holds(self):
        duplicate = truth()["projects"][0]
        result = validate_project_truth_snapshot(truth(projects=[duplicate, dict(duplicate)]))
        self.assertEqual(result["reason"], "PROJECT_TRUTH_DUPLICATE_PROJECT")

    def test_telemetry_hold_still_precedes_verified_truth(self):
        view = build_truth_bound_mission_control_view(
            [mission()],
            [telemetry(evidence_gap_count=1)],
            project_truth_snapshot=truth(),
        )
        self.assertEqual(view["telemetry"][0]["canonical_project_state"], "VERIFIED")
        self.assertEqual(view["telemetry"][0]["effective_action_class"], "HOLD")
        self.assertEqual(view["overall_action_class"], "HOLD")

    def test_controls_remain_advisory_only(self):
        view = build_truth_bound_mission_control_view(
            [mission()],
            [telemetry()],
            [control()],
            project_truth_snapshot=truth(status="APPROVED", reason="EVIDENCE_BOUND_STATE"),
        )
        self.assertEqual(view["control_execution"], "DISABLED")
        self.assertEqual(view["control_intents"][0]["execution_authority"], "NONE")
        self.assertFalse(view["control_intents"][0]["execution_performed"])
        self.assertEqual(view["production_authority"], "HUMAN_ONLY")
        self.assertEqual(view["protected_main_merge"], "HUMAN_ONLY")


if __name__ == "__main__":
    unittest.main()
