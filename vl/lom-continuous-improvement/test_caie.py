import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("caie.py")
spec = importlib.util.spec_from_file_location("lom_caie", MODULE_PATH)
caie = importlib.util.module_from_spec(spec)
spec.loader.exec_module(caie)


def good_task(**overrides):
    values = dict(
        task_id="task-1",
        target="NON_PROD_CODE",
        risk="LOW",
        reversible=True,
        production=False,
        evidence_ref="evidence://ready",
        objective="Improve deterministic test coverage",
        builder_id="builder-a",
        certifier_id="certifier-b",
        budget=caie.Budget(
            max_cost_usd=5.0,
            max_elapsed_seconds=600,
            max_retries=2,
            max_tool_calls=30,
        ),
        trigger=caie.Trigger(
            trigger_id="trg-1",
            trigger_type="CI_FAILURE",
            source_ref="github://run/123",
            evidence_ref="evidence://ci/123",
        ),
    )
    values.update(overrides)
    return caie.ImprovementTask(**values)


GOOD = caie.Evaluation(
    correctness=0.98,
    safety=0.99,
    regression=0.99,
    ux=0.95,
    performance=0.95,
)
BASELINE = caie.Evaluation(
    correctness=0.95,
    safety=0.98,
    regression=0.98,
    ux=0.90,
    performance=0.90,
)
USAGE = caie.Usage(cost_usd=1.0, elapsed_seconds=120, retries=0, tool_calls=8)


class CAIETest(unittest.TestCase):
    def test_happy_path_stops_at_prepare_pr(self):
        task = caie.run_to_prepare_pr(good_task(), GOOD, BASELINE, USAGE)
        self.assertEqual(task.state, "PREPARE_PR")
        self.assertIn("CERTIFIED", task.history)

    def test_production_target_escalates(self):
        engine = caie.CAIE()
        task = good_task(production=True)
        self.assertEqual(engine.qualify(task), "ESCALATE")
        self.assertEqual(task.reason, "PRODUCTION_BOUNDARY")

    def test_human_only_target_escalates(self):
        engine = caie.CAIE()
        task = good_task(target="PROTECTED_MAIN_MERGE")
        self.assertEqual(engine.qualify(task), "ESCALATE")

    def test_unknown_target_holds(self):
        engine = caie.CAIE()
        task = good_task(target="UNKNOWN")
        self.assertEqual(engine.qualify(task), "HOLD")

    def test_irreversible_change_holds(self):
        engine = caie.CAIE()
        task = good_task(reversible=False)
        self.assertEqual(engine.qualify(task), "HOLD")
        self.assertEqual(task.reason, "REVERSIBILITY_REQUIRED")

    def test_self_certification_forbidden(self):
        engine = caie.CAIE()
        task = good_task(certifier_id="builder-a")
        self.assertEqual(engine.qualify(task), "HOLD")
        self.assertEqual(task.reason, "BUILDER_SELF_CERTIFICATION_FORBIDDEN")

    def test_isolated_execution_required(self):
        engine = caie.CAIE()
        task = good_task()
        self.assertEqual(engine.qualify(task), "QUALIFIED")
        self.assertEqual(engine.plan(task), "PLANNED")
        self.assertEqual(engine.enter_sandbox(task, isolated=False), "HOLD")
        self.assertEqual(task.reason, "ISOLATED_EXECUTION_REQUIRED")

    def test_missing_evaluation_evidence_holds(self):
        engine = caie.CAIE()
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        engine.record_test(task, True)
        ev = caie.Evaluation(
            correctness=0.99,
            safety=0.99,
            regression=0.99,
            evidence_complete=False,
        )
        self.assertEqual(engine.score(task, ev, BASELINE, USAGE), "HOLD")

    def test_budget_overrun_rejects(self):
        engine = caie.CAIE()
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        engine.record_test(task, True)
        usage = caie.Usage(cost_usd=10.0, elapsed_seconds=120, retries=0, tool_calls=8)
        self.assertEqual(engine.score(task, GOOD, BASELINE, usage), "REJECT")
        self.assertEqual(task.reason, "BUDGET_OVERRUN")

    def test_negative_usage_is_malformed_and_holds(self):
        engine = caie.CAIE()
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        engine.record_test(task, True)
        usage = caie.Usage(cost_usd=-1.0, elapsed_seconds=120, retries=0, tool_calls=8)
        self.assertEqual(engine.score(task, GOOD, BASELINE, usage), "HOLD")
        self.assertEqual(task.reason, "USAGE_EVIDENCE_INVALID")

    def test_missing_baseline_holds(self):
        engine = caie.CAIE()
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        engine.record_test(task, True)
        self.assertEqual(engine.score(task, GOOD, None, USAGE), "HOLD")
        self.assertEqual(task.reason, "BASELINE_EVIDENCE_REQUIRED")

    def test_internal_state_cannot_be_seeded_via_constructor(self):
        with self.assertRaises(TypeError):
            good_task(state="CERTIFIED")

    def test_prepare_pr_requires_complete_certification_lineage(self):
        engine = caie.CAIE()
        task = good_task()
        task.state = "CERTIFIED"
        self.assertEqual(engine.prepare_pr(task), "HOLD")
        self.assertEqual(task.reason, "CERTIFICATION_LINEAGE_INCOMPLETE")

    def test_quality_regression_rejects(self):
        engine = caie.CAIE()
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        engine.record_test(task, True)
        degraded = caie.Evaluation(
            correctness=0.94,
            safety=0.97,
            regression=0.97,
            ux=0.99,
            performance=0.99,
        )
        self.assertEqual(engine.score(task, degraded, BASELINE, USAGE), "REJECT")
        self.assertEqual(task.reason, "QUALITY_REGRESSION")

    def test_independent_validation_required(self):
        engine = caie.CAIE()
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        engine.record_test(task, True)
        self.assertEqual(engine.score(task, GOOD, BASELINE, USAGE), "SCORED")
        self.assertEqual(engine.certify(task, False, True), "HOLD")

    def test_contradictory_evidence_holds(self):
        engine = caie.CAIE()
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        engine.record_test(task, True)
        engine.score(task, GOOD, BASELINE, USAGE)
        self.assertEqual(engine.certify(task, True, False), "HOLD")
        self.assertEqual(task.reason, "EVIDENCE_CONTRADICTION")

    def test_remediation_is_bounded(self):
        engine = caie.CAIE(max_remediation_attempts=2)
        task = good_task()
        engine.qualify(task)
        engine.plan(task)
        engine.enter_sandbox(task, True)
        self.assertEqual(engine.record_test(task, False), "REMEDIATED")
        self.assertEqual(engine.record_test(task, False), "REMEDIATED")
        self.assertEqual(engine.record_test(task, False), "REJECT")

    def test_protected_merge_and_prod_deploy_are_human_only(self):
        engine = caie.CAIE()
        with self.assertRaises(PermissionError):
            engine.merge_protected_main()
        with self.assertRaises(PermissionError):
            engine.deploy_production()


if __name__ == "__main__":
    unittest.main()
