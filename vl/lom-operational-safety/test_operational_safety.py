import unittest
from pathlib import Path

from action_registry import ActionRegistry
from delegation import validate_actor_separation, validate_attempt, validate_delegation
from evidence_replay import ReplayGuard, validate_evidence
from event_ledger import AppendOnlyEventLedger
from red_team_chaos_lab import run_suite

ROOT = Path(__file__).resolve().parent


class OperationalSafetyTests(unittest.TestCase):
    def setUp(self):
        self.registry = ActionRegistry.from_path(ROOT / "action-registry.json")
        self.parent = {
            "environment": "NON_PRODUCTION",
            "capability_ids": ["cap.test.execute", "cap.report.render"],
            "risk_ceiling": "LOW",
            "expires_at_epoch": 2000,
            "max_attempts": 2,
        }

    def test_registered_action_delegates(self):
        result = self.registry.authorize("RUN_TEST", "cap.test.execute", "LOW", True, False)
        self.assertEqual(result["decision"], "DELEGATE")

    def test_unregistered_action_holds(self):
        result = self.registry.authorize("UNREGISTERED_ACTION", "cap.test.execute", "LOW", True, False)
        self.assertEqual(result, {"decision": "HOLD", "reason": "UNREGISTERED_ACTION"})

    def test_human_only_escalates(self):
        result = self.registry.authorize("PRODUCTION_RELEASE", "cap.test.execute", "LOW", True, False)
        self.assertEqual(result["decision"], "ESCALATE")

    def test_capability_mismatch_holds(self):
        result = self.registry.authorize("RUN_TEST", "cap.report.render", "LOW", True, False)
        self.assertEqual(result["reason"], "CAPABILITY_MISMATCH")

    def test_production_boundary_escalates(self):
        result = self.registry.authorize("RUN_TEST", "cap.test.execute", "LOW", True, True)
        self.assertEqual(result["reason"], "PRODUCTION_BOUNDARY")

    def test_executor_validator_collision_holds(self):
        result = validate_actor_separation("actor-a", "actor-a")
        self.assertEqual(result["reason"], "EXECUTOR_VALIDATOR_COLLISION")

    def test_remediator_validator_collision_holds(self):
        result = validate_actor_separation("executor", "validator", "validator")
        self.assertEqual(result["reason"], "REMEDIATOR_VALIDATOR_COLLISION")

    def test_distinct_actors_allow(self):
        result = validate_actor_separation("executor", "validator", "remediator")
        self.assertEqual(result["decision"], "ALLOW")

    def test_expired_delegation_holds(self):
        child = dict(self.parent, expires_at_epoch=1000)
        result = validate_delegation(self.parent, child, 1000)
        self.assertEqual(result["reason"], "DELEGATION_EXPIRED")

    def test_widened_capability_holds(self):
        child = dict(self.parent, capability_ids=["cap.test.execute", "cap.unknown"])
        result = validate_delegation(self.parent, child, 1000)
        self.assertEqual(result["reason"], "DELEGATION_CAPABILITY_WIDENED")

    def test_widened_risk_holds(self):
        child = dict(self.parent, risk_ceiling="HIGH")
        result = validate_delegation(self.parent, child, 1000)
        self.assertEqual(result["reason"], "DELEGATION_RISK_WIDENED")

    def test_widened_attempts_holds(self):
        child = dict(self.parent, max_attempts=3)
        result = validate_delegation(self.parent, child, 1000)
        self.assertEqual(result["reason"], "DELEGATION_ATTEMPTS_WIDENED")

    def test_non_production_delegation_allows(self):
        child = dict(self.parent, capability_ids=["cap.test.execute"], expires_at_epoch=1500, max_attempts=1)
        result = validate_delegation(self.parent, child, 1000)
        self.assertEqual(result["decision"], "ALLOW")

    def test_attempt_budget_exhaustion_holds(self):
        self.assertEqual(validate_attempt(3, 2)["reason"], "ATTEMPT_BUDGET_EXHAUSTED")

    def test_duplicate_replay_holds(self):
        guard = ReplayGuard()
        self.assertEqual(guard.claim("run-1", "obj-1", "key-1")["decision"], "ALLOW")
        self.assertEqual(guard.claim("run-1", "obj-1", "key-1")["reason"], "DUPLICATE_OR_REPLAY")

    def test_stale_evidence_holds(self):
        result = validate_evidence("PASS", 100, 1000, 100)
        self.assertEqual(result["reason"], "STALE_EVIDENCE")

    def test_contradictory_evidence_holds(self):
        result = validate_evidence("PASS", 950, 1000, 100, contradictory=True)
        self.assertEqual(result["reason"], "CONTRADICTORY_EVIDENCE")

    def test_fresh_evidence_allows(self):
        result = validate_evidence("PASS", 950, 1000, 100)
        self.assertEqual(result["decision"], "ALLOW")

    def test_append_only_ledger_hash_chain(self):
        ledger = AppendOnlyEventLedger()
        ledger.append("run-1", "obj-1", "executor", "RUN_TEST", ["ev-1"], "PLANNED", "RUNNING", "start", 1000)
        ledger.append("run-1", "obj-1", "validator", "RUN_TEST", ["ev-2"], "RUNNING", "COMPLETE", "validated", 1001)
        self.assertTrue(ledger.verify())
        self.assertEqual(ledger.events[1]["sequence"], 2)

    def test_ledger_rejects_unknown_state(self):
        ledger = AppendOnlyEventLedger()
        with self.assertRaisesRegex(ValueError, "UNKNOWN_STATE"):
            ledger.append("run-1", "obj-1", "executor", "RUN_TEST", [], "PLANNED", "MYSTERY", "bad", 1000)

    def test_ledger_rejects_replace_delete(self):
        ledger = AppendOnlyEventLedger()
        with self.assertRaisesRegex(RuntimeError, "APPEND_ONLY_LEDGER"):
            ledger.replace()
        with self.assertRaisesRegex(RuntimeError, "APPEND_ONLY_LEDGER"):
            ledger.delete()

    def test_red_team_chaos_suite_blocks_all_registered_attacks(self):
        result = run_suite()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["reason"], "ALL_ATTACKS_FAIL_CLOSED")
        self.assertEqual(result["failed_count"], 0)
        self.assertTrue(result["production_locked"])
        self.assertEqual(result["execution_authority"], "NONE")
        self.assertFalse(result["execution_performed"])


if __name__ == "__main__":
    unittest.main()
