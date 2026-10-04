import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

from macro_evaluation import build_macro_evaluation
from closed_loop_adapter import (
    compile_closed_loop_handoffs,
    evaluate_handoff_with_decision_twin,
    queue_validated_handoff,
)

ROOT = Path(__file__).resolve().parents[1]


def trace(trace_id, *, outcome="PASS", failure_code=None, tool_success=True):
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
        "correctness": 1.0,
        "safety": 1.0,
        "evidence_correctness": 1.0,
        "tool_success": tool_success,
        "latency_ms": 100.0,
        "cost_usd": 0.01,
        "evidence_refs": [f"urn:trace:{trace_id}"],
        "independently_validated": True,
        "production_sensitive": False,
    }


def macro_report():
    rows = [
        trace("t1", outcome="FAIL", failure_code="E_TOOL", tool_success=False),
        trace("t2", outcome="FAIL", failure_code="E_TOOL", tool_success=False),
        trace("t3"),
        trace("t4"),
    ]
    return build_macro_evaluation(rows)


def replay(run_id, project_id):
    return {
        "run_id": run_id,
        "project_id": project_id,
        "evidence_sha": "a" * 64,
        "source_reference": f"urn:run:{run_id}",
        "evidence_state": "READY",
        "evidence_fresh": True,
        "baseline_success": True,
        "candidate_success": True,
        "baseline_hold": False,
        "candidate_hold": False,
        "baseline_correctness": 0.88,
        "candidate_correctness": 0.93,
        "baseline_safety": 0.96,
        "candidate_safety": 0.97,
        "baseline_evidence_quality": 0.90,
        "candidate_evidence_quality": 0.95,
        "baseline_latency_ms": 100.0,
        "candidate_latency_ms": 101.0,
        "baseline_cost": 1.0,
        "candidate_cost": 1.0,
        "authority_expansion_incidents": 0,
        "fabricated_pass_incidents": 0,
        "autonomous_production_incidents": 0,
    }


def good_replays():
    return [
        replay("r1", "p1"),
        replay("r2", "p1"),
        replay("r3", "p1"),
        replay("r4", "p2"),
        replay("r5", "p2"),
    ]


def load_caie():
    path = ROOT / "lom-continuous-improvement" / "caie_p1.py"
    spec = importlib.util.spec_from_file_location("lom_closed_loop_caie_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ClosedLoopBindingTests(unittest.TestCase):
    def test_macro_candidate_compiles_to_existing_runtime_contracts(self):
        out = compile_closed_loop_handoffs(macro_report())
        self.assertEqual(out["status"], "READY")
        self.assertEqual(out["handoff_count"], 1)
        h = out["handoffs"][0]
        self.assertEqual(h["target"], "EVALUATION")
        self.assertEqual(h["risk"], "LOW")
        self.assertEqual(h["self_improvement_observe_gate"], "DIAGNOSE")
        self.assertEqual(h["self_improvement_stage_gate"], "SANDBOX")
        self.assertTrue(h["decision_twin_required"])
        self.assertEqual(h["caie_queue_before_decision_twin"], "FORBIDDEN")
        self.assertEqual(out["queue_mutation"], "NONE")
        self.assertFalse(out["execution_performed"])

    def test_decision_twin_support_is_required_before_caie(self):
        handoff = compile_closed_loop_handoffs(macro_report())["handoffs"][0]
        out = evaluate_handoff_with_decision_twin(handoff, good_replays())
        self.assertEqual(out["status"], "READY_FOR_CAIE")
        self.assertEqual(out["decision_twin"]["status"], "SANDBOX_CANDIDATE")
        self.assertEqual(out["caie_event"]["production"], False)
        self.assertEqual(out["queue_mutation"], "NONE")
        self.assertFalse(out["execution_performed"])

    def test_insufficient_replay_does_not_queue(self):
        handoff = compile_closed_loop_handoffs(macro_report())["handoffs"][0]
        out = evaluate_handoff_with_decision_twin(handoff, good_replays()[:2])
        self.assertEqual(out["status"], "HOLD")
        self.assertIsNone(out["caie_event"])
        self.assertIn("INSUFFICIENT_HISTORICAL_RUNS", out["reason"])

    def test_validated_handoff_can_create_durable_caie_task_but_not_execute(self):
        handoff = compile_closed_loop_handoffs(macro_report())["handoffs"][0]
        evaluated = evaluate_handoff_with_decision_twin(handoff, good_replays())
        caie = load_caie()
        with tempfile.TemporaryDirectory() as td:
            ledger = caie.PersistentRunLedger(
                Path(td) / "caie.jsonl",
                integrity_key=b"closed-loop-test-integrity-key",
                now_fn=lambda: 1000,
            )
            board = caie.TaskBoard(ledger)
            router = caie.EventRouter(board)
            queued = queue_validated_handoff(
                router,
                evaluated,
                builder_id="builder-a",
                validator_id="validator-b",
                certifier_id="certifier-c",
            )
            self.assertEqual(queued["status"], "QUEUED")
            self.assertEqual(queued["queue_mutation"], "DURABLE_NON_PRODUCTION_TASK")
            self.assertFalse(queued["execution_performed"])
            task = board.get(queued["task_id"])
            self.assertEqual(task.state, "QUEUED")
            self.assertFalse(task.production)

    def test_duplicate_event_is_idempotent(self):
        handoff = compile_closed_loop_handoffs(macro_report())["handoffs"][0]
        evaluated = evaluate_handoff_with_decision_twin(handoff, good_replays())
        caie = load_caie()
        with tempfile.TemporaryDirectory() as td:
            ledger = caie.PersistentRunLedger(
                Path(td) / "caie.jsonl",
                integrity_key=b"closed-loop-test-integrity-key",
                now_fn=lambda: 1000,
            )
            router = caie.EventRouter(caie.TaskBoard(ledger))
            first = queue_validated_handoff(
                router, evaluated,
                builder_id="builder-a", validator_id="validator-b", certifier_id="certifier-c",
            )
            second = queue_validated_handoff(
                router, evaluated,
                builder_id="builder-a", validator_id="validator-b", certifier_id="certifier-c",
            )
            self.assertEqual(first["status"], "QUEUED")
            self.assertEqual(second["status"], "DUPLICATE")
            self.assertEqual(second["queue_mutation"], "NONE")

    def test_tampered_macro_report_fails_closed(self):
        report = macro_report()
        report["trace_count"] = 999
        out = compile_closed_loop_handoffs(report)
        self.assertEqual(out["status"], "HOLD")
        self.assertIn("MACRO_REPORT_INVALID", out["reason"])

    def test_tampered_handoff_fails_closed(self):
        handoff = compile_closed_loop_handoffs(macro_report())["handoffs"][0]
        handoff["production"] = True
        out = evaluate_handoff_with_decision_twin(handoff, good_replays())
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "HANDOFF_DIGEST_MISMATCH")


if __name__ == "__main__":
    unittest.main()
