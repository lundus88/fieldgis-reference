import copy
import unittest

from frontier_evaluation import (
    AdversarialAuditEvidence,
    BenchmarkObservation,
    DIMENSIONS,
    build_frontier_scorecard,
    improvement_candidates,
)


def audit(status="PASS", failed=0):
    return AdversarialAuditEvidence(
        suite_id="lom-red-team-chaos",
        evidence_ref="urn:lom:redteam:run-1",
        evaluator_id="security-evaluator",
        executor_id="lom-runtime",
        scenario_count=14,
        passed_count=14-failed,
        failed_count=failed,
        status=status,
        evidence_fresh=True,
        independent_validation=True,
    )


def observation(dimension, *, score=0.99, external=False, ref_score=0.90, suffix="1"):
    return BenchmarkObservation(
        benchmark_id=f"{dimension}-{suffix}",
        dimension=dimension,
        task_class=f"{dimension}_TASK",
        candidate_system="LOM",
        candidate_score=score,
        evaluator_id=f"eval-{dimension}-{suffix}",
        executor_id="lom-runtime",
        evidence_ref=f"urn:benchmark:{dimension}:{suffix}",
        evidence_fresh=True,
        independent_validation=True,
        external_comparable=external,
        reference_system="frontier-reference" if external else None,
        reference_score=ref_score if external else None,
    )


def full_rows(*, external=False, score=0.99, ref_score=0.90):
    return [
        observation(d, score=score, external=external, ref_score=ref_score)
        for d in DIMENSIONS
    ]


class FrontierEvaluationTests(unittest.TestCase):
    def test_internal_readiness_cannot_claim_world_best(self):
        out = build_frontier_scorecard(full_rows(), adversarial_audit=audit(), candidate_system="LOM")
        self.assertEqual(out["status"], "INTERNAL_FRONTIER_READY")
        self.assertEqual(out["reason"], "EXTERNAL_COMPARABLE_EVIDENCE_REQUIRED")
        self.assertEqual(out["world_best_claim"], "FORBIDDEN")
        self.assertFalse(out["frontier_candidate_is_world_best"])
        self.assertEqual(out["execution_authority"], "NONE")
        self.assertEqual(out["autonomous_ceiling"], "PREPARE_PR")
        self.assertEqual(out["production_authority"], "HUMAN_ONLY")

    def test_external_comparisons_can_create_frontier_candidate_not_world_best(self):
        out = build_frontier_scorecard(
            full_rows(external=True, score=0.99, ref_score=0.90),
            adversarial_audit=audit(),
            candidate_system="LOM",
        )
        self.assertEqual(out["status"], "FRONTIER_CANDIDATE")
        self.assertEqual(out["world_best_claim"], "FORBIDDEN")
        self.assertTrue(out["third_party_review_required_for_global_claim"])
        self.assertFalse(out["frontier_candidate_is_world_best"])

    def test_missing_dimension_holds_and_generates_propose_only_gap(self):
        rows = full_rows()[:-1]
        out = build_frontier_scorecard(rows, adversarial_audit=audit(), candidate_system="LOM")
        self.assertEqual(out["status"], "HOLD")
        gaps = improvement_candidates(out)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["dimension"], "GOVERNANCE")
        self.assertEqual(gaps[0]["disposition"], "PROPOSE_ONLY")
        self.assertEqual(gaps[0]["authority_effect"], "NONE")

    def test_below_threshold_holds(self):
        rows = full_rows()
        rows[0] = observation("REASONING", score=0.50)
        out = build_frontier_scorecard(rows, adversarial_audit=audit(), candidate_system="LOM")
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["dimensions"]["REASONING"]["status"], "BELOW_THRESHOLD")

    def test_adversarial_failure_holds(self):
        out = build_frontier_scorecard(
            full_rows(),
            adversarial_audit=audit(status="FAIL", failed=1),
            candidate_system="LOM",
        )
        self.assertEqual(out["status"], "HOLD")

    def test_self_evaluation_forbidden(self):
        bad = observation("REASONING")
        bad = BenchmarkObservation(**{**bad.__dict__, "evaluator_id": "lom-runtime"})
        out = build_frontier_scorecard(
            [bad] + [observation(d) for d in DIMENSIONS if d != "REASONING"],
            adversarial_audit=audit(),
            candidate_system="LOM",
        )
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["reason"], "SELF_EVALUATION_FORBIDDEN")

    def test_stale_benchmark_holds(self):
        bad = observation("REASONING")
        bad = BenchmarkObservation(**{**bad.__dict__, "evidence_fresh": False})
        out = build_frontier_scorecard(
            [bad] + [observation(d) for d in DIMENSIONS if d != "REASONING"],
            adversarial_audit=audit(),
            candidate_system="LOM",
        )
        self.assertEqual(out["reason"], "BENCHMARK_EVIDENCE_STALE")

    def test_tampered_scorecard_cannot_generate_learning_candidate(self):
        out = build_frontier_scorecard(full_rows()[:-1], adversarial_audit=audit(), candidate_system="LOM")
        tampered = copy.deepcopy(out)
        tampered["dimensions"]["GOVERNANCE"]["status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "FRONTIER_SCORECARD_DIGEST_MISMATCH"):
            improvement_candidates(tampered)

    def test_duplicate_benchmark_id_holds(self):
        rows = full_rows()
        rows.append(observation("REASONING"))
        out = build_frontier_scorecard(rows, adversarial_audit=audit(), candidate_system="LOM")
        self.assertEqual(out["reason"], "DUPLICATE_BENCHMARK_ID")

    def test_reference_fields_without_external_comparable_hold(self):
        bad = BenchmarkObservation(
            benchmark_id="bad",
            dimension="REASONING",
            task_class="X",
            candidate_system="LOM",
            candidate_score=0.99,
            evaluator_id="independent",
            executor_id="lom-runtime",
            evidence_ref="urn:benchmark:bad",
            evidence_fresh=True,
            independent_validation=True,
            external_comparable=False,
            reference_system="other",
            reference_score=0.9,
        )
        out = build_frontier_scorecard(
            [bad] + [observation(d) for d in DIMENSIONS if d != "REASONING"],
            adversarial_audit=audit(),
            candidate_system="LOM",
        )
        self.assertEqual(out["reason"], "REFERENCE_FIELDS_REQUIRE_EXTERNAL_COMPARABLE")


if __name__ == "__main__":
    unittest.main()
