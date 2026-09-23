import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).with_name("caie.py")
spec = importlib.util.spec_from_file_location("lom_caie", MODULE_PATH)
caie = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = caie
spec.loader.exec_module(caie)

KEY = b"test-evidence-key-32-bytes-minimum!"
BAD_KEY = b"different-test-key-32-bytes-value!!"
NOW = 2_000_000_000
SUBJECT = "urn:lom:task:task-1"


def sign(kind, payload, *, issuer="evidence-service", issued_at=NOW - 60,
         expires_at=NOW + 600, key=KEY, subject=SUBJECT, evidence_id=None):
    return caie.EvidenceRecord.sign(
        key=key,
        evidence_id=evidence_id or f"ev-{kind.lower()}",
        kind=kind,
        issuer=issuer,
        subject_ref=subject,
        provenance_ref=f"evidence://source/{kind.lower()}",
        issued_at=issued_at,
        expires_at=expires_at,
        payload_digest=caie.digest_payload(payload),
    )


QUALIFICATION_PAYLOAD = {"objective": "Improve deterministic test coverage"}
TRIGGER_PAYLOAD = {"trigger_id": "trg-1", "source_ref": "github://run/123"}
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


def good_task(**overrides):
    values = dict(
        task_id="task-1",
        target="NON_PROD_CODE",
        risk="LOW",
        reversible=True,
        production=False,
        objective="Improve deterministic test coverage",
        builder_id="builder-a",
        certifier_id="certifier-b",
        budget=caie.Budget(
            max_cost_usd=5.0,
            max_elapsed_seconds=600,
            max_retries=2,
            max_tool_calls=30,
        ),
        qualification_evidence=sign("QUALIFICATION", QUALIFICATION_PAYLOAD),
        trigger=caie.Trigger(
            trigger_id="trg-1",
            trigger_type="CI_FAILURE",
            source_ref="github://run/123",
            evidence=sign("TRIGGER", TRIGGER_PAYLOAD),
        ),
    )
    values.update(overrides)
    return caie.ImprovementTask(**values)


def evaluation_evidence(evaluation=GOOD, **kwargs):
    return sign("EVALUATION", evaluation.payload(), **kwargs)


def baseline_evidence(baseline=BASELINE, **kwargs):
    return sign("BASELINE", baseline.payload(), **kwargs)


def usage_evidence(usage=USAGE, **kwargs):
    return sign(
        "USAGE",
        {
            "cost_usd": usage.cost_usd,
            "elapsed_seconds": usage.elapsed_seconds,
            "retries": usage.retries,
            "tool_calls": usage.tool_calls,
        },
        **kwargs,
    )


def certification_evidence(*, certifier_id="certifier-b", independent=True,
                           consistent=True, **kwargs):
    payload = {
        "task_id": "task-1",
        "certifier_id": certifier_id,
        "independent_validation": independent,
        "evidence_consistent": consistent,
    }
    evidence = sign("CERTIFICATION", payload, issuer=certifier_id, **kwargs)
    return caie.CertificationEvidence(
        certifier_id=certifier_id,
        independent_validation=independent,
        evidence_consistent=consistent,
        evidence=evidence,
    )


def engine(**kwargs):
    return caie.CAIE(evidence_key=KEY, now_fn=lambda: NOW, **kwargs)


def advance_to_tested(e, task):
    assert e.qualify(task) == "QUALIFIED"
    assert e.plan(task) == "PLANNED"
    assert e.enter_sandbox(task, True) == "SANDBOX"
    assert e.record_test(task, True) == "TESTED"


def advance_to_scored(e, task, *, evaluation=GOOD, baseline=BASELINE, usage=USAGE):
    advance_to_tested(e, task)
    return e.score(
        task,
        evaluation=evaluation,
        evaluation_evidence=evaluation_evidence(evaluation),
        baseline=baseline,
        baseline_evidence=baseline_evidence(baseline),
        usage=usage,
        usage_evidence=usage_evidence(usage),
    )


class CAIEHardeningTest(unittest.TestCase):
    def test_happy_path_stops_at_prepare_pr(self):
        task = good_task()
        result = caie.run_to_prepare_pr(
            evidence_key=KEY,
            task=task,
            evaluation=GOOD,
            evaluation_evidence=evaluation_evidence(),
            baseline=BASELINE,
            baseline_evidence=baseline_evidence(),
            usage=USAGE,
            usage_evidence=usage_evidence(),
            certification=certification_evidence(),
            now_fn=lambda: NOW,
        )
        self.assertEqual(result.state, "PREPARE_PR")
        self.assertEqual(
            result.history,
            ("DISCOVERED", "QUALIFIED", "PLANNED", "SANDBOX",
             "TESTED", "SCORED", "CERTIFIED", "PREPARE_PR"),
        )

    def test_short_evidence_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "EVIDENCE_KEY_TOO_SHORT"):
            caie.CAIE(evidence_key=b"short", now_fn=lambda: NOW)

    def test_production_target_escalates(self):
        e = engine()
        task = good_task(production=True)
        self.assertEqual(e.qualify(task), "ESCALATE")
        self.assertEqual(task.reason, "PRODUCTION_BOUNDARY")

    def test_human_only_target_escalates(self):
        e = engine()
        task = good_task(target="PROTECTED_MAIN_MERGE")
        self.assertEqual(e.qualify(task), "ESCALATE")

    def test_unknown_target_holds(self):
        e = engine()
        task = good_task(target="UNKNOWN")
        self.assertEqual(e.qualify(task), "HOLD")

    def test_irreversible_change_holds(self):
        e = engine()
        task = good_task(reversible=False)
        self.assertEqual(e.qualify(task), "HOLD")
        self.assertEqual(task.reason, "REVERSIBILITY_REQUIRED")

    def test_self_certification_forbidden_at_qualification(self):
        e = engine()
        task = good_task(certifier_id="builder-a")
        self.assertEqual(e.qualify(task), "HOLD")
        self.assertEqual(task.reason, "BUILDER_SELF_CERTIFICATION_FORBIDDEN")

    def test_stale_qualification_evidence_holds(self):
        stale = sign(
            "QUALIFICATION",
            QUALIFICATION_PAYLOAD,
            issued_at=NOW - 7200,
            expires_at=NOW + 600,
        )
        e = engine(max_evidence_age_seconds=3600)
        task = good_task(qualification_evidence=stale)
        self.assertEqual(e.qualify(task), "HOLD")
        self.assertEqual(task.reason, "QUALIFICATION_EVIDENCE_INVALID")

    def test_expired_trigger_evidence_holds(self):
        expired = sign(
            "TRIGGER",
            TRIGGER_PAYLOAD,
            issued_at=NOW - 600,
            expires_at=NOW - 1,
        )
        task = good_task(
            trigger=caie.Trigger(
                trigger_id="trg-1",
                trigger_type="CI_FAILURE",
                source_ref="github://run/123",
                evidence=expired,
            )
        )
        e = engine()
        self.assertEqual(e.qualify(task), "HOLD")
        self.assertEqual(task.reason, "TRIGGER_EVIDENCE_INVALID")

    def test_forged_evidence_signature_holds(self):
        forged = sign("QUALIFICATION", QUALIFICATION_PAYLOAD, key=BAD_KEY)
        e = engine()
        task = good_task(qualification_evidence=forged)
        self.assertEqual(e.qualify(task), "HOLD")
        self.assertEqual(task.reason, "QUALIFICATION_EVIDENCE_INVALID")

    def test_provenance_is_required(self):
        valid = sign("QUALIFICATION", QUALIFICATION_PAYLOAD)
        malformed = caie.EvidenceRecord(
            evidence_id=valid.evidence_id,
            kind=valid.kind,
            issuer=valid.issuer,
            subject_ref=valid.subject_ref,
            provenance_ref="not-a-provenance-uri",
            issued_at=valid.issued_at,
            expires_at=valid.expires_at,
            payload_digest=valid.payload_digest,
            signature=valid.signature,
        )
        e = engine()
        task = good_task(qualification_evidence=malformed)
        self.assertEqual(e.qualify(task), "HOLD")

    def test_isolated_execution_required(self):
        e = engine()
        task = good_task()
        self.assertEqual(e.qualify(task), "QUALIFIED")
        self.assertEqual(e.plan(task), "PLANNED")
        self.assertEqual(e.enter_sandbox(task, False), "HOLD")

    def test_evaluation_digest_mismatch_holds(self):
        e = engine()
        task = good_task()
        advance_to_tested(e, task)
        other = caie.Evaluation(0.99, 0.99, 0.99, 0.99, 0.99)
        self.assertEqual(
            e.score(
                task,
                evaluation=GOOD,
                evaluation_evidence=evaluation_evidence(other),
                baseline=BASELINE,
                baseline_evidence=baseline_evidence(),
                usage=USAGE,
                usage_evidence=usage_evidence(),
            ),
            "HOLD",
        )
        self.assertEqual(task.reason, "EVALUATION_DIGEST_MISMATCH")

    def test_negative_usage_holds(self):
        e = engine()
        task = good_task()
        advance_to_tested(e, task)
        usage = caie.Usage(cost_usd=-1.0, elapsed_seconds=120, retries=0, tool_calls=8)
        self.assertEqual(
            e.score(
                task,
                evaluation=GOOD,
                evaluation_evidence=evaluation_evidence(),
                baseline=BASELINE,
                baseline_evidence=baseline_evidence(),
                usage=usage,
                usage_evidence=usage_evidence(usage),
            ),
            "HOLD",
        )
        self.assertEqual(task.reason, "USAGE_EVIDENCE_INVALID")

    def test_budget_overrun_rejects(self):
        e = engine()
        task = good_task()
        advance_to_tested(e, task)
        usage = caie.Usage(cost_usd=10.0, elapsed_seconds=120, retries=0, tool_calls=8)
        self.assertEqual(
            e.score(
                task,
                evaluation=GOOD,
                evaluation_evidence=evaluation_evidence(),
                baseline=BASELINE,
                baseline_evidence=baseline_evidence(),
                usage=usage,
                usage_evidence=usage_evidence(usage),
            ),
            "REJECT",
        )
        self.assertEqual(task.reason, "BUDGET_OVERRUN")

    def test_missing_baseline_holds(self):
        e = engine()
        task = good_task()
        advance_to_tested(e, task)
        self.assertEqual(
            e.score(
                task,
                evaluation=GOOD,
                evaluation_evidence=evaluation_evidence(),
                baseline=None,
                baseline_evidence=None,
                usage=USAGE,
                usage_evidence=usage_evidence(),
            ),
            "HOLD",
        )
        self.assertEqual(task.reason, "BASELINE_EVIDENCE_REQUIRED")

    def test_quality_regression_rejects(self):
        e = engine()
        task = good_task()
        advance_to_tested(e, task)
        degraded = caie.Evaluation(
            correctness=0.94,
            safety=0.97,
            regression=0.97,
            ux=0.99,
            performance=0.99,
        )
        self.assertEqual(
            e.score(
                task,
                evaluation=degraded,
                evaluation_evidence=evaluation_evidence(degraded),
                baseline=BASELINE,
                baseline_evidence=baseline_evidence(),
                usage=USAGE,
                usage_evidence=usage_evidence(),
            ),
            "REJECT",
        )

    def test_certifier_identity_mismatch_holds(self):
        e = engine()
        task = good_task()
        self.assertEqual(advance_to_scored(e, task), "SCORED")
        cert = certification_evidence(certifier_id="certifier-c")
        self.assertEqual(e.certify(task, cert), "HOLD")
        self.assertEqual(task.reason, "CERTIFIER_IDENTITY_MISMATCH")

    def test_unsigned_or_wrong_key_certification_holds(self):
        e = engine()
        task = good_task()
        self.assertEqual(advance_to_scored(e, task), "SCORED")
        cert = certification_evidence(key=BAD_KEY)
        self.assertEqual(e.certify(task, cert), "HOLD")
        self.assertEqual(task.reason, "CERTIFICATION_EVIDENCE_INVALID")

    def test_independent_validation_required(self):
        e = engine()
        task = good_task()
        self.assertEqual(advance_to_scored(e, task), "SCORED")
        cert = certification_evidence(independent=False)
        self.assertEqual(e.certify(task, cert), "HOLD")
        self.assertEqual(task.reason, "INDEPENDENT_VALIDATION_REQUIRED")

    def test_contradictory_evidence_holds(self):
        e = engine()
        task = good_task()
        self.assertEqual(advance_to_scored(e, task), "SCORED")
        cert = certification_evidence(consistent=False)
        self.assertEqual(e.certify(task, cert), "HOLD")
        self.assertEqual(task.reason, "EVIDENCE_CONTRADICTION")

    def test_direct_state_mutation_cannot_prepare_pr(self):
        e = engine()
        task = good_task()
        task._state = "CERTIFIED"
        self.assertEqual(e.prepare_pr(task), "HOLD")
        self.assertEqual(task.reason, "TRANSITION_LEDGER_INVALID")

    def test_ledger_tampering_cannot_prepare_pr(self):
        e = engine()
        task = good_task()
        self.assertEqual(advance_to_scored(e, task), "SCORED")
        self.assertEqual(e.certify(task, certification_evidence()), "CERTIFIED")
        original = task._ledger[-1]
        task._ledger[-1] = caie.TransitionRecord(
            sequence=original.sequence,
            from_state=original.from_state,
            to_state=original.to_state,
            reason="FORGED_REASON",
            previous_digest=original.previous_digest,
            digest=original.digest,
        )
        self.assertEqual(e.prepare_pr(task), "HOLD")
        self.assertEqual(task.reason, "TRANSITION_LEDGER_INVALID")

    def test_certification_from_another_engine_cannot_prepare_pr(self):
        first = engine()
        task = good_task()
        self.assertEqual(advance_to_scored(first, task), "SCORED")
        self.assertEqual(first.certify(task, certification_evidence()), "CERTIFIED")
        second = engine()
        self.assertEqual(second.prepare_pr(task), "HOLD")

    def test_remediation_is_bounded_and_valid_lineage_can_prepare(self):
        e = engine(max_remediation_attempts=2)
        task = good_task()
        self.assertEqual(e.qualify(task), "QUALIFIED")
        self.assertEqual(e.plan(task), "PLANNED")
        self.assertEqual(e.enter_sandbox(task, True), "SANDBOX")
        self.assertEqual(e.record_test(task, False), "REMEDIATED")
        self.assertEqual(e.record_test(task, True), "TESTED")
        self.assertEqual(
            e.score(
                task,
                evaluation=GOOD,
                evaluation_evidence=evaluation_evidence(),
                baseline=BASELINE,
                baseline_evidence=baseline_evidence(),
                usage=USAGE,
                usage_evidence=usage_evidence(),
            ),
            "SCORED",
        )
        self.assertEqual(e.certify(task, certification_evidence()), "CERTIFIED")
        self.assertEqual(e.prepare_pr(task), "PREPARE_PR")
        self.assertIn("REMEDIATED", task.history)

    def test_remediation_exhaustion_rejects(self):
        e = engine(max_remediation_attempts=2)
        task = good_task()
        self.assertEqual(e.qualify(task), "QUALIFIED")
        self.assertEqual(e.plan(task), "PLANNED")
        self.assertEqual(e.enter_sandbox(task, True), "SANDBOX")
        self.assertEqual(e.record_test(task, False), "REMEDIATED")
        self.assertEqual(e.record_test(task, False), "REMEDIATED")
        self.assertEqual(e.record_test(task, False), "REJECT")

    def test_protected_merge_and_prod_deploy_are_human_only(self):
        e = engine()
        with self.assertRaises(PermissionError):
            e.merge_protected_main()
        with self.assertRaises(PermissionError):
            e.deploy_production()


if __name__ == "__main__":
    unittest.main()
