import copy
import hashlib
import json
import unittest

from causal_memory_adapter import (
    build_causal_memory_projection,
    digest,
    validate_causal_memory_projection,
)


def plain_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def world_graph():
    body = {
        "schema": "lom.world-state-graph/1",
        "status": "READY",
        "reason": "WORLD_STATE_GRAPH_READY",
        "source_registry_version": "2.0",
        "project_count": 1,
        "objective_count": 1,
        "dependency_count": 0,
        "nodes": [
            {
                "node_id": "project:vl",
                "type": "PROJECT",
                "project_id": "vl",
                "name": "VL",
                "repository": "lundus88/fieldgis-reference",
                "source_mode": "READ_ONLY",
                "twin_status": "READY",
                "action_class": "AUTO_PREPARE",
                "reason": "BOUNDED_NONPRODUCTION_PREPARATION_ELIGIBLE",
                "next_action": "PREPARE_PR",
                "snapshot_digest": "sha256:test",
                "dependency_attention_from": [],
                "attention_required": False,
            },
            {
                "node_id": "objective:portfolio:vl:readiness",
                "type": "OBJECTIVE",
                "objective_id": "portfolio:vl:readiness",
                "project_id": "vl",
            },
        ],
        "edges": [
            {
                "edge_id": "objective-link:vl",
                "type": "HAS_OBJECTIVE",
                "from": "project:vl",
                "to": "objective:portfolio:vl:readiness",
            }
        ],
        "violations": [],
        "attention_required": False,
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "self_approval": "FORBIDDEN",
        "database_mutation": "DISABLED",
        "connector_execution": "DISABLED",
    }
    return {**body, "graph_digest": digest(body)}


def ledger():
    body = {
        "sequence": 1,
        "run_id": "run-1",
        "objective_id": "portfolio:vl:readiness",
        "actor_id": "planner",
        "action_id": "RUN_TEST",
        "evidence_refs": ["urn:evidence:test"],
        "from_state": "PLANNED",
        "to_state": "COMPLETE",
        "reason": "validated",
        "timestamp_epoch": 1000,
        "prev_hash": "GENESIS",
    }
    return [{**body, "event_hash": plain_hash(body)}]


def decisions():
    return [{
        "decision_id": "d1",
        "action": "RUN_TEST",
        "evidence_state": "READY",
        "outcome": "PASS",
        "human_verdict": "APPROVED",
        "rationale": "test evidence passed",
    }]


def binding(event_hash):
    return [{
        "binding_id": "c1",
        "project_id": "vl",
        "objective_id": "portfolio:vl:readiness",
        "decision_id": "d1",
        "event_hash": event_hash,
        "cause": "The validated test action resolved the bounded readiness condition.",
        "lesson": "Use the same independently validated test route for the same bounded condition.",
        "evidence_refs": ["urn:evidence:test", "urn:independent-validation:1"],
        "independently_validated": True,
        "causal_confidence": 0.95,
    }]


def failure_signal(environment="NON_PRODUCTION"):
    signal = {
        "failure_id": "f1",
        "run_id": "run-2",
        "project_id": "vl",
        "component": "ci",
        "failure_class": "TEST_FAILURE",
        "error_code": "E_TEST",
        "environment": environment,
        "risk": "LOW",
        "reversible": True,
        "evidence_refs": ["urn:failure:1"],
        "timestamp_epoch": 1100,
    }
    fp = plain_hash({
        "project_id": signal["project_id"],
        "component": signal["component"],
        "failure_class": signal["failure_class"],
        "error_code": signal["error_code"],
        "environment": signal["environment"],
    })
    return signal, fp


class CausalMemoryAdapterTests(unittest.TestCase):
    def test_builds_evidence_backed_causal_projection(self):
        events = ledger()
        signal, fp = failure_signal()
        p = build_causal_memory_projection(
            world_graph(),
            events,
            decisions(),
            causal_bindings=binding(events[0]["event_hash"]),
            failure_signals=[signal],
            recovery_attempts=[{
                "attempt_id": "a1",
                "run_id": "run-2",
                "failure_fingerprint": fp,
                "action": "RERUN_BOUNDED_TEST",
                "outcome": "RECOVERED",
                "evidence_refs": ["urn:recovery:1"],
                "independently_validated": True,
                "timestamp_epoch": 1200,
            }],
        )
        self.assertEqual(p["status"], "READY")
        self.assertEqual(p["causal_record_count"], 1)
        self.assertEqual(p["known_good_recovery_count"], 1)
        self.assertFalse(p["causality_inferred_from_sequence"])
        self.assertEqual(validate_causal_memory_projection(p)["status"], "READY")
        self.assertEqual(p["execution_authority"], "NONE")
        self.assertEqual(p["memory_persistence"], "NONE")

    def test_projection_is_deterministic(self):
        events = ledger()
        a = build_causal_memory_projection(
            world_graph(), events, decisions(),
            causal_bindings=binding(events[0]["event_hash"]),
        )
        b = build_causal_memory_projection(
            world_graph(), list(reversed(events)), list(reversed(decisions())),
            causal_bindings=list(reversed(binding(events[0]["event_hash"]))),
        )
        self.assertEqual(a["projection_digest"], b["projection_digest"])

    def test_tampered_ledger_fails_closed(self):
        events = ledger()
        events[0]["reason"] = "tampered"
        p = build_causal_memory_projection(world_graph(), events, decisions())
        self.assertEqual(p["status"], "HOLD")
        self.assertEqual(p["reason"], "EVENT_LEDGER_HASH_INVALID")

    def test_sequence_is_not_treated_as_causality(self):
        p = build_causal_memory_projection(world_graph(), ledger(), decisions())
        self.assertEqual(p["status"], "READY")
        self.assertEqual(p["causal_record_count"], 0)
        self.assertFalse(p["causality_inferred_from_sequence"])

    def test_unvalidated_causal_binding_fails_closed(self):
        events = ledger()
        bad = binding(events[0]["event_hash"])
        bad[0]["independently_validated"] = False
        p = build_causal_memory_projection(
            world_graph(), events, decisions(), causal_bindings=bad
        )
        self.assertEqual(p["status"], "HOLD")
        self.assertEqual(p["reason"], "CAUSAL_INDEPENDENT_VALIDATION_REQUIRED")

    def test_action_mismatch_fails_closed(self):
        events = ledger()
        d = decisions()
        d[0]["action"] = "DIFFERENT_ACTION"
        p = build_causal_memory_projection(
            world_graph(), events, d,
            causal_bindings=binding(events[0]["event_hash"]),
        )
        self.assertEqual(p["status"], "HOLD")
        self.assertEqual(p["reason"], "CAUSAL_ACTION_MISMATCH")

    def test_unvalidated_recovered_attempt_fails_closed(self):
        signal, fp = failure_signal()
        p = build_causal_memory_projection(
            world_graph(), ledger(), decisions(),
            failure_signals=[signal],
            recovery_attempts=[{
                "attempt_id": "a1",
                "run_id": "run-2",
                "failure_fingerprint": fp,
                "action": "FIX",
                "outcome": "RECOVERED",
                "evidence_refs": ["urn:recovery:1"],
                "independently_validated": False,
                "timestamp_epoch": 1200,
            }],
        )
        self.assertEqual(p["status"], "HOLD")
        self.assertEqual(p["reason"], "RECOVERY_REQUIRES_INDEPENDENT_VALIDATION")

    def test_failed_attempt_is_history_not_known_good(self):
        signal, fp = failure_signal()
        p = build_causal_memory_projection(
            world_graph(), ledger(), decisions(),
            failure_signals=[signal],
            recovery_attempts=[{
                "attempt_id": "a1",
                "run_id": "run-2",
                "failure_fingerprint": fp,
                "action": "FIX",
                "outcome": "FAILED",
                "evidence_refs": ["urn:recovery:failed"],
                "independently_validated": False,
                "timestamp_epoch": 1200,
            }],
        )
        self.assertEqual(p["status"], "READY")
        self.assertEqual(p["known_good_recovery_count"], 0)
        self.assertEqual(p["historical_recovery_count"], 1)

    def test_production_recovery_not_promoted_to_causal_lesson(self):
        signal, fp = failure_signal(environment="PRODUCTION")
        p = build_causal_memory_projection(
            world_graph(), ledger(), decisions(),
            failure_signals=[signal],
            recovery_attempts=[{
                "attempt_id": "a1",
                "run_id": "run-2",
                "failure_fingerprint": fp,
                "action": "FIX",
                "outcome": "RECOVERED",
                "evidence_refs": ["urn:prod-recovery"],
                "independently_validated": True,
                "timestamp_epoch": 1200,
            }],
        )
        self.assertEqual(p["status"], "HOLD")
        self.assertEqual(p["reason"], "PRODUCTION_RECOVERY_CAUSAL_PROMOTION_FORBIDDEN")

    def test_projection_tamper_detected(self):
        p = build_causal_memory_projection(world_graph(), ledger(), decisions())
        t = copy.deepcopy(p)
        t["causal_record_count"] = 99
        self.assertEqual(
            validate_causal_memory_projection(t)["reason"],
            "CAUSAL_PROJECTION_DIGEST_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
