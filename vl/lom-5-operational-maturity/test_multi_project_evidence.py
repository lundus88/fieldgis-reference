import copy
import unittest

from multi_project_evidence import evaluate_registry


def hex64(char: str) -> str:
    return char * 64


def hex40(char: str) -> str:
    return char * 40


def record(run_id: str, project_id: str, outcome: str = "PASS", attempts: int = 1):
    remediation = []
    if outcome == "REMEDIATED":
        remediation = [{"attempt": 1, "reason": "bounded fixture remediation", "result": "PASS"}]
    return {
        "run_id": run_id,
        "project_id": project_id,
        "evidence_state": "VERIFIED",
        "request_id": f"req-{run_id}",
        "app_spec_sha256": hex64("a"),
        "context_policy_sha256": hex64("b"),
        "model_routing_decision_sha256": hex64("c"),
        "capability_scope": ["repo.read", "ci.inspect"],
        "resource_scope": [f"repo:{project_id}"],
        "token_budget": 10000,
        "cost_budget": 10.0,
        "time_budget_seconds": 600,
        "retry_budget": 2,
        "source_commit_sha": hex40("d"),
        "artifact_sha256": hex64("e"),
        "qa_security_evidence": [{"kind": "ci", "status": "SUCCESS", "ref": f"ci-{run_id}"}],
        "independent_validation": {"validator": "independent", "status": "PASS" if outcome not in {"HOLD", "BLOCKED"} else outcome},
        "remediation_history": remediation,
        "release_candidate_state": "RC" if outcome in {"PASS", "REMEDIATED"} else "HOLD",
        "human_decision": "ACCEPT" if outcome in {"PASS", "REMEDIATED"} else "HOLD",
        "release_outcome": "NO_PRODUCTION_ACTION",
        "rollback_audit_linkage": f"audit-{run_id}",
        "final_outcome": outcome,
        "attempts": attempts,
        "elapsed_seconds": 120,
        "estimated_model_tool_cost": 1.25,
        "budget_overrun": False,
        "authority_expansion_incident": False,
        "fabricated_pass_incident": False,
        "production_approval": False,
        "builder_self_certified": False,
        "multi_agent_delegation": {"demonstrated": run_id == "g4", "authority_expanded": False},
    }


def complete_registry():
    return {
        "schema": "lom.operational-maturity-evidence/1",
        "records": [
            record("g1", "ebkl", "PASS", 1),
            record("g2", "ebkl", "BLOCKED", 1),
            record("g3", "lunduslead", "REMEDIATED", 2),
            record("g4", "kontenstudio", "PASS", 1),
        ],
    }


class OperationalMaturityEvidenceTests(unittest.TestCase):
    def test_complete_multi_project_evidence_passes(self):
        result = evaluate_registry(complete_registry())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["metrics"]["budget_overruns"], 0)
        self.assertEqual(result["metrics"]["authority_expansion_incidents"], 0)
        self.assertEqual(result["metrics"]["fabricated_pass_incidents"], 0)
        self.assertTrue(result["criteria"]["fail_closed_case_present"])
        self.assertTrue(result["criteria"]["remediation_case_present"])
        self.assertTrue(result["criteria"]["bounded_multi_agent_delegation_present"])

    def test_partial_record_cannot_count_as_verified(self):
        registry = complete_registry()
        registry["records"][3] = {"run_id": "g4", "project_id": "kontenstudio", "evidence_state": "PARTIAL"}
        result = evaluate_registry(registry)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["criteria"]["at_least_four_verified_runs"])
        self.assertIn("g4", result["partial_run_ids"])

    def test_verified_record_missing_required_fields_holds(self):
        registry = complete_registry()
        del registry["records"][0]["human_decision"]
        result = evaluate_registry(registry)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "INVALID_EVIDENCE_RECORD")

    def test_authority_expansion_is_fail_closed(self):
        registry = complete_registry()
        registry["records"][1]["authority_expansion_incident"] = True
        result = evaluate_registry(registry)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "SAFETY_INVARIANT_VIOLATION")

    def test_fabricated_pass_is_fail_closed(self):
        registry = complete_registry()
        registry["records"][0]["fabricated_pass_incident"] = True
        result = evaluate_registry(registry)
        self.assertEqual(result["reason"], "SAFETY_INVARIANT_VIOLATION")

    def test_budget_overrun_is_fail_closed(self):
        registry = complete_registry()
        registry["records"][2]["budget_overrun"] = True
        result = evaluate_registry(registry)
        self.assertEqual(result["reason"], "SAFETY_INVARIANT_VIOLATION")

    def test_production_approval_is_forbidden(self):
        registry = complete_registry()
        registry["records"][0]["production_approval"] = True
        result = evaluate_registry(registry)
        self.assertEqual(result["reason"], "SAFETY_INVARIANT_VIOLATION")

    def test_builder_self_certification_is_forbidden(self):
        registry = complete_registry()
        registry["records"][0]["builder_self_certified"] = True
        result = evaluate_registry(registry)
        self.assertEqual(result["reason"], "SAFETY_INVARIANT_VIOLATION")

    def test_three_projects_are_required(self):
        registry = complete_registry()
        registry["records"][3]["project_id"] = "lunduslead"
        result = evaluate_registry(registry)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["criteria"]["at_least_three_projects"])

    def test_fail_closed_case_is_required(self):
        registry = complete_registry()
        registry["records"][1]["final_outcome"] = "PASS"
        result = evaluate_registry(registry)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["criteria"]["fail_closed_case_present"])

    def test_remediation_case_is_required(self):
        registry = complete_registry()
        registry["records"][2]["final_outcome"] = "PASS"
        registry["records"][2]["remediation_history"] = []
        result = evaluate_registry(registry)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["criteria"]["remediation_case_present"])

    def test_bounded_multi_agent_evidence_is_required(self):
        registry = complete_registry()
        for item in registry["records"]:
            item["multi_agent_delegation"] = {"demonstrated": False, "authority_expanded": False}
        result = evaluate_registry(registry)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["criteria"]["bounded_multi_agent_delegation_present"])

    def test_registry_fingerprint_changes_with_evidence(self):
        first = evaluate_registry(complete_registry())["registry_sha256"]
        changed = complete_registry()
        changed["records"][0]["elapsed_seconds"] = 121
        second = evaluate_registry(changed)["registry_sha256"]
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
