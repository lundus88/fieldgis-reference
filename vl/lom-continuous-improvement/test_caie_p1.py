import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).with_name("caie_p1.py")
spec = importlib.util.spec_from_file_location("lom_caie_p1", MODULE_PATH)
p1 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p1
spec.loader.exec_module(p1)

KEY = b"caie-p1-test-ledger-integrity-key!"
NOW = 2_000_000_000


class Harness:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "run-ledger.jsonl"
        self.ledger = p1.PersistentRunLedger(
            self.path,
            integrity_key=KEY,
            now_fn=lambda: NOW,
        )
        self.board = p1.TaskBoard(self.ledger)
        self.router = p1.EventRouter(self.board)

    def close(self):
        self.temp.cleanup()

    def event(self, **overrides):
        values = dict(
            event_id="event-1",
            event_type="CI_FAILURE",
            objective="Repair deterministic CI regression",
            target="NON_PROD_CODE",
            risk="LOW",
            reversible=True,
            production=False,
            evidence_ref="evidence://ci/run-123",
        )
        values.update(overrides)
        return p1.ImprovementEvent(**values)

    def accept(self, **event_overrides):
        decision = self.router.ingest(
            self.event(**event_overrides),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
            max_remediation_attempts=2,
        )
        assert decision.task_id is not None
        return decision.task_id


def good_registry():
    registry = p1.ScorerRegistry(overall_threshold=0.90)
    registry.register(
        "correctness",
        lambda context: context["correctness"],
        threshold=0.95,
        weight=2.0,
        hard_gate=True,
    )
    registry.register(
        "safety",
        lambda context: context["safety"],
        threshold=0.95,
        weight=2.0,
        hard_gate=True,
    )
    registry.register(
        "performance",
        lambda context: context["performance"],
        threshold=0.80,
        weight=1.0,
    )
    return registry


def passing_attempt():
    return p1.AttemptResult(
        tests_passed=True,
        evidence_ref="evidence://attempt/pass",
        context={"correctness": 0.99, "safety": 0.99, "performance": 0.95},
    )


def passing_validator(task, attempt):
    return p1.ValidationResult(
        passed=True,
        validator_id=task.validator_id,
        evidence_ref="evidence://validation/pass",
    )


def passing_certifier(task, report):
    return p1.CertificationResult(
        passed=True,
        certifier_id=task.certifier_id,
        evidence_ref="evidence://certification/pass",
        authority_ceiling="PREPARE_PR",
    )


class LedgerAndBoardTest(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_empty_ledger_is_valid(self):
        self.assertTrue(self.h.ledger.verify())
        self.assertEqual(self.h.ledger.records(), tuple())

    def test_ledger_persists_and_rebuilds_task_after_restart(self):
        task_id = self.h.accept()
        self.h.board.transition(task_id, "ACTIVE", "START")
        second_ledger = p1.PersistentRunLedger(
            self.h.path,
            integrity_key=KEY,
            now_fn=lambda: NOW,
        )
        second_board = p1.TaskBoard(second_ledger)
        restored = second_board.get(task_id)
        self.assertEqual(restored.state, "ACTIVE")
        self.assertEqual(restored.objective, "Repair deterministic CI regression")

    def test_ledger_tampering_is_detected(self):
        self.h.ledger.append(
            "EVENT_REJECTED",
            task_id="",
            payload={
                "external_event_id": "x",
                "disposition": "HOLD",
                "reason": "TEST",
            },
        )
        raw = self.h.path.read_text()
        self.h.path.write_text(raw.replace('"reason":"TEST"', '"reason":"FORGED"'))
        with self.assertRaises(p1.LedgerIntegrityError):
            p1.PersistentRunLedger(self.h.path, integrity_key=KEY)

    def test_wrong_integrity_key_rejects_existing_ledger(self):
        self.h.accept()
        with self.assertRaises(p1.LedgerIntegrityError):
            p1.PersistentRunLedger(
                self.h.path,
                integrity_key=b"different-ledger-integrity-key-123",
            )

    def test_semantically_illegal_persisted_transition_fails_closed(self):
        self.h.ledger.append(
            "TASK_STATE",
            task_id="unknown-task",
            payload={"state": "ACTIVE", "reason": "FORGED"},
        )
        with self.assertRaises(p1.LedgerIntegrityError):
            p1.TaskBoard(self.h.ledger)

    def test_terminal_task_cannot_transition(self):
        task_id = self.h.accept()
        self.h.board.transition(task_id, "ESCALATE", "STOP")
        with self.assertRaises(p1.TaskStateError):
            self.h.board.transition(task_id, "ACTIVE", "ILLEGAL")

    def test_attempt_requires_active_or_remediating(self):
        task_id = self.h.accept()
        with self.assertRaises(p1.TaskStateError):
            self.h.board.start_attempt(task_id)


class EventRouterTest(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_event_is_accepted_and_task_is_queued(self):
        task_id = self.h.accept()
        task = self.h.board.get(task_id)
        self.assertEqual(task.state, "QUEUED")
        self.assertFalse(task.production)

    def test_duplicate_event_is_idempotent(self):
        first = self.h.router.ingest(
            self.h.event(),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        count = len(self.h.ledger.records())
        second = self.h.router.ingest(
            self.h.event(),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        self.assertEqual(second.disposition, "DUPLICATE")
        self.assertEqual(second.task_id, first.task_id)
        self.assertEqual(len(self.h.ledger.records()), count)

    def test_duplicate_rejected_event_is_also_idempotent(self):
        event = self.h.event(event_id="prod-1", production=True)
        first = self.h.router.ingest(
            event,
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        count = len(self.h.ledger.records())
        second = self.h.router.ingest(
            event,
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        self.assertEqual(first.disposition, "ESCALATE")
        self.assertEqual(second.disposition, "DUPLICATE")
        self.assertEqual(len(self.h.ledger.records()), count)

    def test_restart_after_task_create_before_ack_is_idempotent(self):
        event = self.h.event(event_id="crash-window")
        task_id = "caie-" + __import__("hashlib").sha256(
            event.event_id.encode("utf-8")
        ).hexdigest()[:16]
        self.h.board.create(
            task_id=task_id,
            objective=event.objective,
            target=event.target,
            risk=event.risk,
            reversible=event.reversible,
            production=event.production,
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
            max_remediation_attempts=2,
            source_event_id=event.event_id,
        )
        count = len(self.h.ledger.records())

        restarted_ledger = p1.PersistentRunLedger(
            self.h.path,
            integrity_key=KEY,
            now_fn=lambda: NOW,
        )
        restarted_board = p1.TaskBoard(restarted_ledger)
        restarted_router = p1.EventRouter(restarted_board)
        decision = restarted_router.ingest(
            event,
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        self.assertEqual(decision.disposition, "DUPLICATE")
        self.assertEqual(decision.task_id, task_id)
        self.assertEqual(len(restarted_ledger.records()), count)

    def test_production_event_escalates(self):
        decision = self.h.router.ingest(
            self.h.event(production=True),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        self.assertEqual(decision.disposition, "ESCALATE")
        self.assertEqual(decision.reason, "PRODUCTION_BOUNDARY")

    def test_human_only_event_escalates(self):
        decision = self.h.router.ingest(
            self.h.event(target="PROTECTED_MAIN_MERGE"),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        self.assertEqual(decision.disposition, "ESCALATE")

    def test_missing_evidence_holds(self):
        decision = self.h.router.ingest(
            self.h.event(evidence_ref=""),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
        )
        self.assertEqual(decision.disposition, "HOLD")

    def test_separation_of_duties_is_required(self):
        decision = self.h.router.ingest(
            self.h.event(),
            builder_id="same",
            validator_id="same",
            certifier_id="certifier-c",
        )
        self.assertEqual(decision.disposition, "HOLD")
        self.assertEqual(decision.reason, "SEPARATION_OF_DUTIES_REQUIRED")


class ScorerRegistryTest(unittest.TestCase):
    def test_hard_gate_failure_blocks(self):
        registry = good_registry()
        report = registry.evaluate(
            {"correctness": 0.90, "safety": 0.99, "performance": 1.0}
        )
        self.assertFalse(report.passed)
        self.assertIn("HARD_GATE_FAILED:correctness", report.reason)

    def test_weighted_success(self):
        report = good_registry().evaluate(
            {"correctness": 0.99, "safety": 0.99, "performance": 0.95}
        )
        self.assertTrue(report.passed)
        self.assertGreaterEqual(report.overall, 0.90)

    def test_empty_registry_fails_closed(self):
        report = p1.ScorerRegistry().evaluate({})
        self.assertFalse(report.passed)
        self.assertEqual(report.reason, "NO_SCORERS_REGISTERED")

    def test_invalid_scorer_result_fails_closed(self):
        registry = p1.ScorerRegistry()
        registry.register("bad", lambda context: float("nan"), threshold=0.5)
        report = registry.evaluate({})
        self.assertFalse(report.passed)
        self.assertEqual(report.reason, "SCORER_INVALID:bad")

    def test_duplicate_scorer_is_rejected(self):
        registry = p1.ScorerRegistry()
        registry.register("x", lambda context: 1.0, threshold=0.5)
        with self.assertRaises(ValueError):
            registry.register("x", lambda context: 1.0, threshold=0.5)


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.close()

    def test_happy_path_stops_at_prepare_pr(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())
        final = runtime.run(
            task_id,
            executor=lambda task, attempt: passing_attempt(),
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "PREPARE_PR")
        self.assertEqual(final.attempts, 1)
        release = [
            r for r in self.h.ledger.records()
            if r.event_type == "RELEASE_CANDIDATE"
        ][-1]
        self.assertFalse(release.payload["merge_executed"])
        self.assertTrue(release.payload["production_locked"])

    def test_failed_first_attempt_is_remediated_then_recovers(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())

        def executor(task, attempt):
            if attempt == 1:
                return p1.AttemptResult(
                    tests_passed=False,
                    evidence_ref="evidence://attempt/fail",
                    context={"correctness": 0.5, "safety": 0.99, "performance": 0.9},
                )
            return passing_attempt()

        final = runtime.run(
            task_id,
            executor=executor,
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "PREPARE_PR")
        self.assertEqual(final.attempts, 2)

    def test_executor_exception_can_be_remediated(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())

        def executor(task, attempt):
            if attempt == 1:
                raise RuntimeError("simulated")
            return passing_attempt()

        final = runtime.run(
            task_id,
            executor=executor,
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "PREPARE_PR")
        self.assertEqual(final.attempts, 2)

    def test_remediation_budget_is_enforced(self):
        decision = self.h.router.ingest(
            self.h.event(event_id="budget-1"),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
            max_remediation_attempts=1,
        )
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())
        final = runtime.run(
            decision.task_id,
            executor=lambda task, attempt: p1.AttemptResult(
                tests_passed=False,
                evidence_ref="evidence://attempt/fail",
                context={"correctness": 0.5, "safety": 0.5, "performance": 0.5},
            ),
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "REJECT")
        self.assertEqual(final.attempts, 2)
        self.assertEqual(final.reason, "REMEDIATION_BUDGET_EXHAUSTED")

    def test_hard_gate_failure_remediates_and_then_passes(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())

        def executor(task, attempt):
            correctness = 0.90 if attempt == 1 else 0.99
            return p1.AttemptResult(
                tests_passed=True,
                evidence_ref=f"evidence://attempt/{attempt}",
                context={
                    "correctness": correctness,
                    "safety": 0.99,
                    "performance": 0.95,
                },
            )

        final = runtime.run(
            task_id,
            executor=executor,
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "PREPARE_PR")
        self.assertEqual(final.attempts, 2)

    def test_attempt_cannot_cross_production_boundary(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())
        final = runtime.run(
            task_id,
            executor=lambda task, attempt: p1.AttemptResult(
                tests_passed=True,
                evidence_ref="evidence://attempt/x",
                context={"correctness": 1.0, "safety": 1.0, "performance": 1.0},
                production=True,
            ),
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "ESCALATE")
        self.assertEqual(final.reason, "ATTEMPT_CROSSED_PRODUCTION_BOUNDARY")

    def test_invalid_attempt_authority_scope_holds(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())
        final = runtime.run(
            task_id,
            executor=lambda task, attempt: p1.AttemptResult(
                tests_passed=True,
                evidence_ref="evidence://attempt/x",
                context={"correctness": 1.0, "safety": 1.0, "performance": 1.0},
                authority_scope="PRODUCTION",
            ),
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "HOLD")
        self.assertEqual(final.reason, "ATTEMPT_AUTHORITY_SCOPE_INVALID")

    def test_validator_identity_is_enforced(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())

        def wrong_validator(task, attempt):
            return p1.ValidationResult(
                True,
                "someone-else",
                "evidence://validation/wrong",
            )

        final = runtime.run(
            task_id,
            executor=lambda task, attempt: passing_attempt(),
            validator=wrong_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "HOLD")
        self.assertEqual(final.reason, "VALIDATOR_IDENTITY_INVALID")

    def test_certifier_identity_is_enforced(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())

        def wrong_certifier(task, report):
            return p1.CertificationResult(
                True,
                "someone-else",
                "evidence://certification/wrong",
            )

        final = runtime.run(
            task_id,
            executor=lambda task, attempt: passing_attempt(),
            validator=passing_validator,
            certifier=wrong_certifier,
        )
        self.assertEqual(final.state, "HOLD")
        self.assertEqual(final.reason, "CERTIFIER_IDENTITY_INVALID")

    def test_certifier_cannot_widen_authority_ceiling(self):
        task_id = self.h.accept()
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())

        def widened(task, report):
            return p1.CertificationResult(
                True,
                task.certifier_id,
                "evidence://certification/pass",
                authority_ceiling="PRODUCTION_DEPLOY",
            )

        final = runtime.run(
            task_id,
            executor=lambda task, attempt: passing_attempt(),
            validator=passing_validator,
            certifier=widened,
        )
        self.assertEqual(final.state, "HOLD")
        self.assertEqual(final.reason, "AUTHORITY_CEILING_INVALID")

    def test_empty_scorer_registry_cannot_prepare_pr(self):
        decision = self.h.router.ingest(
            self.h.event(event_id="no-scorers"),
            builder_id="builder-a",
            validator_id="validator-b",
            certifier_id="certifier-c",
            max_remediation_attempts=0,
        )
        runtime = p1.AutonomousRemediationRuntime(
            self.h.board,
            p1.ScorerRegistry(),
        )
        final = runtime.run(
            decision.task_id,
            executor=lambda task, attempt: passing_attempt(),
            validator=passing_validator,
            certifier=passing_certifier,
        )
        self.assertEqual(final.state, "REJECT")
        self.assertEqual(final.reason, "NO_SCORERS_REGISTERED")

    def test_protected_merge_and_production_deploy_remain_human_only(self):
        runtime = p1.AutonomousRemediationRuntime(self.h.board, good_registry())
        with self.assertRaises(PermissionError):
            runtime.merge_protected_main()
        with self.assertRaises(PermissionError):
            runtime.deploy_production()


if __name__ == "__main__":
    unittest.main()
