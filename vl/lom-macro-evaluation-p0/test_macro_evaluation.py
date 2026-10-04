import copy
import unittest

from macro_evaluation import build_macro_evaluation, digest, validate_macro_evaluation


def trace(
    trace_id,
    *,
    outcome="PASS",
    failure_code=None,
    correctness=1.0,
    safety=1.0,
    evidence_correctness=1.0,
    tool_success=True,
):
    return {
        "trace_id": trace_id,
        "project_id": "vl",
        "task_class": "CODING_DEBUGGING",
        "component": "planner",
        "model_id": "model-x",
        "model_version": "v1",
        "tool_id": "github",
        "outcome": outcome,
        "failure_code": failure_code,
        "correctness": correctness,
        "safety": safety,
        "evidence_correctness": evidence_correctness,
        "tool_success": tool_success,
        "latency_ms": 100 + int(trace_id[-1]) if trace_id[-1].isdigit() else 100,
        "cost_usd": 0.01,
        "evidence_refs": [f"urn:trace:{trace_id}"],
        "independently_validated": True,
        "production_sensitive": False,
    }


def causal_projection(error_code="E_TOOL"):
    recovery = [{
        "record_id": "recovery:a1",
        "type": "RECOVERY_CAUSAL",
        "project_id": "vl",
        "failure_fingerprint": "fp",
        "component": "planner",
        "failure_class": "TOOL_FAILURE",
        "error_code": error_code,
        "environment": "NON_PRODUCTION",
        "action": "REROUTE_TOOL",
        "outcome": "RECOVERED",
        "evidence_refs": ["urn:recovery:a1"],
        "independently_validated": True,
        "lesson": "Reroute the bounded tool call.",
    }]
    body = {
        "schema": "lom.causal-memory-projection/1",
        "status": "READY",
        "reason": "EVIDENCE_BACKED_CAUSAL_MEMORY_READY",
        "world_graph_digest": "sha256:world",
        "causal_records": [],
        "recovery_records": recovery,
        "historical_recovery_records": [],
        "causal_record_count": 0,
        "known_good_recovery_count": 1,
        "historical_recovery_count": 0,
        "causality_inferred_from_sequence": False,
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "self_approval": "FORBIDDEN",
        "database_mutation": "DISABLED",
        "connector_execution": "DISABLED",
        "memory_persistence": "NONE",
    }
    return {**body, "projection_digest": digest(body)}


class MacroEvaluationTests(unittest.TestCase):
    def test_detects_recurrent_pattern_and_proposes_only(self):
        rows = [
            trace("t1", outcome="FAIL", failure_code="E_TOOL", tool_success=False),
            trace("t2", outcome="FAIL", failure_code="E_TOOL", tool_success=False),
            trace("t3"),
            trace("t4"),
        ]
        report = build_macro_evaluation(rows)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["recurrent_pattern_count"], 1)
        self.assertEqual(report["learning_candidate_count"], 1)
        self.assertEqual(report["learning_candidates"][0]["disposition"], "PROPOSE_ONLY")
        self.assertEqual(report["learning_candidates"][0]["target"], "EVALUATION")
        self.assertEqual(report["execution_authority"], "NONE")
        self.assertEqual(report["production_authority"], "HUMAN_ONLY")
        self.assertEqual(report["memory_persistence"], "NONE")
        self.assertEqual(validate_macro_evaluation(report)["status"], "READY")

    def test_causal_memory_can_upgrade_observation_to_supported_candidate(self):
        rows = [
            trace("t1", outcome="FAIL", failure_code="E_TOOL", tool_success=False),
            trace("t2", outcome="FAIL", failure_code="E_TOOL", tool_success=False),
            trace("t3"),
        ]
        report = build_macro_evaluation(rows, causal_projection=causal_projection())
        pattern = report["failure_patterns"][0]
        candidate = report["learning_candidates"][0]
        self.assertEqual(pattern["causal_status"], "CAUSAL_SUPPORTED")
        self.assertEqual(candidate["causal_status"], "CAUSAL_SUPPORTED")
        self.assertEqual(candidate["target"], "NON_PROD_WORKFLOW")
        self.assertIn("REROUTE_TOOL", candidate["proposed_change"])

    def test_trace_order_does_not_change_report_digest(self):
        rows = [
            trace("t1", outcome="FAIL", failure_code="E_TOOL"),
            trace("t2", outcome="FAIL", failure_code="E_TOOL"),
            trace("t3"),
        ]
        a = build_macro_evaluation(rows)
        b = build_macro_evaluation(list(reversed(rows)))
        self.assertEqual(a["report_digest"], b["report_digest"])

    def test_insufficient_recurrence_is_not_promoted(self):
        rows = [
            trace("t1", outcome="FAIL", failure_code="E_ONE"),
            trace("t2"),
            trace("t3"),
        ]
        report = build_macro_evaluation(rows)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["recurrent_pattern_count"], 0)
        self.assertEqual(report["learning_candidate_count"], 0)

    def test_duplicate_trace_fails_closed(self):
        report = build_macro_evaluation([trace("t1"), trace("t1")])
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["reason"], "DUPLICATE_TRACE_ID")

    def test_production_sensitive_trace_fails_closed(self):
        bad = trace("t1")
        bad["production_sensitive"] = True
        report = build_macro_evaluation([bad])
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["reason"], "PRODUCTION_SENSITIVE_TRACE_FORBIDDEN")

    def test_invalid_numeric_measurement_fails_closed(self):
        bad = trace("t1")
        bad["correctness"] = 1.5
        report = build_macro_evaluation([bad])
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["reason"], "TRACE_CORRECTNESS_INVALID")

    def test_tampered_causal_projection_fails_closed(self):
        p = causal_projection()
        p["known_good_recovery_count"] = 99
        report = build_macro_evaluation([trace("t1")], causal_projection=p)
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["reason"], "CAUSAL_PROJECTION_DIGEST_MISMATCH")

    def test_task_health_alerts_on_population_degradation(self):
        rows = [
            trace("t1", correctness=0.7),
            trace("t2", correctness=0.8),
            trace("t3", correctness=0.8),
        ]
        report = build_macro_evaluation(rows)
        health = report["task_health"][0]
        self.assertEqual(health["status"], "ALERT")
        self.assertIn("CORRECTNESS_BELOW_GATE", health["reasons"])

    def test_report_tamper_is_detected(self):
        report = build_macro_evaluation([trace("t1"), trace("t2"), trace("t3")])
        tampered = copy.deepcopy(report)
        tampered["trace_count"] = 999
        self.assertEqual(
            validate_macro_evaluation(tampered)["reason"],
            "MACRO_EVALUATION_DIGEST_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
