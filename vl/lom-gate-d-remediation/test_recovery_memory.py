import unittest

from recovery_memory import FailureSignal, RecoveryAttempt, RecurrentFailureMemory


def failure(**overrides):
    data = dict(
        failure_id="f-1",
        run_id="run-1",
        project_id="ebkl",
        component="vercel-preview",
        failure_class="CONFIGURATION",
        error_code="MISSING_PREVIEW_ENV",
        environment="NON_PRODUCTION",
        risk="LOW",
        reversible=True,
        evidence_refs=("ev-1",),
        timestamp_epoch=1000,
    )
    data.update(overrides)
    return FailureSignal(**data)


def attempt(signal, **overrides):
    data = dict(
        attempt_id="a-1",
        run_id=signal.run_id,
        failure_fingerprint=signal.fingerprint,
        action="SET_PREVIEW_ENV",
        outcome="FAILED",
        evidence_refs=("ev-a1",),
        independently_validated=False,
        timestamp_epoch=1001,
    )
    data.update(overrides)
    return RecoveryAttempt(**data)


class RecurrentFailureMemoryTests(unittest.TestCase):
    def test_recurrence_count_spans_runs(self):
        memory = RecurrentFailureMemory()
        first = failure()
        second = failure(failure_id="f-2", run_id="run-2", timestamp_epoch=1002)
        memory.observe(first)
        snapshot = memory.observe(second)
        self.assertEqual(snapshot["recurrence_count"], 2)
        self.assertEqual(snapshot["distinct_run_count"], 2)

    def test_failure_id_collision_rejected(self):
        memory = RecurrentFailureMemory()
        memory.observe(failure())
        with self.assertRaisesRegex(ValueError, "FAILURE_ID_COLLISION"):
            memory.observe(failure(error_code="OTHER"))

    def test_missing_failure_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError, "EVIDENCE_REQUIRED"):
            RecurrentFailureMemory().observe(failure(evidence_refs=()))

    def test_unknown_attempt_fingerprint_rejected(self):
        memory = RecurrentFailureMemory()
        signal = failure()
        with self.assertRaisesRegex(ValueError, "UNKNOWN_FAILURE_FINGERPRINT"):
            memory.record_attempt(attempt(signal))

    def test_recovered_attempt_requires_independent_validation(self):
        memory = RecurrentFailureMemory()
        signal = failure()
        memory.observe(signal)
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRES_INDEPENDENT_VALIDATION"):
            memory.record_attempt(attempt(signal, outcome="RECOVERED"))

    def test_known_good_route_is_preferred(self):
        memory = RecurrentFailureMemory()
        signal = failure()
        memory.observe(signal)
        memory.record_attempt(attempt(signal, outcome="RECOVERED", independently_validated=True))
        result = memory.recommend(
            signal,
            delegated_actions=["SET_PREVIEW_ENV"],
            candidate_actions=["SET_PREVIEW_ENV"],
        )
        self.assertEqual(result["decision"], "PREPARE_REMEDIATION")
        self.assertEqual(result["reason"], "KNOWN_GOOD_RECOVERY_ROUTE")
        self.assertEqual(result["action"], "SET_PREVIEW_ENV")

    def test_failed_route_is_not_repeated_when_fallback_exists(self):
        memory = RecurrentFailureMemory()
        signal = failure()
        memory.observe(signal)
        memory.record_attempt(attempt(signal))
        result = memory.recommend(
            signal,
            delegated_actions=["SET_PREVIEW_ENV", "REDEPLOY_PREVIEW"],
            candidate_actions=["SET_PREVIEW_ENV", "REDEPLOY_PREVIEW"],
        )
        self.assertEqual(result["reason"], "SAFE_FALLBACK_ROUTE")
        self.assertEqual(result["action"], "REDEPLOY_PREVIEW")

    def test_all_failed_single_occurrence_holds(self):
        memory = RecurrentFailureMemory()
        signal = failure()
        memory.observe(signal)
        memory.record_attempt(attempt(signal))
        result = memory.recommend(
            signal,
            delegated_actions=["SET_PREVIEW_ENV"],
            candidate_actions=["SET_PREVIEW_ENV"],
        )
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason"], "RECOVERY_LOOP_PREVENTED")

    def test_recurrent_all_failed_requires_human(self):
        memory = RecurrentFailureMemory()
        first = failure()
        second = failure(failure_id="f-2", run_id="run-2", timestamp_epoch=1002)
        memory.observe(first)
        memory.observe(second)
        memory.record_attempt(attempt(first))
        result = memory.recommend(
            second,
            delegated_actions=["SET_PREVIEW_ENV"],
            candidate_actions=["SET_PREVIEW_ENV"],
        )
        self.assertEqual(result["decision"], "ESCALATE")
        self.assertEqual(result["reason"], "RECURRENT_FAILURE_REQUIRES_HUMAN")

    def test_production_never_gets_autonomous_route(self):
        memory = RecurrentFailureMemory()
        signal = failure(environment="PRODUCTION")
        memory.observe(signal)
        result = memory.recommend(signal, delegated_actions=["X"], candidate_actions=["X"])
        self.assertEqual(result["decision"], "ESCALATE")
        self.assertEqual(result["reason"], "PRODUCTION_BOUNDARY")
        self.assertEqual(result["execution_authority"], "NONE")

    def test_non_low_risk_escalates(self):
        memory = RecurrentFailureMemory()
        signal = failure(risk="MEDIUM")
        memory.observe(signal)
        result = memory.recommend(signal, delegated_actions=["X"], candidate_actions=["X"])
        self.assertEqual(result["reason"], "RISK_THRESHOLD_EXCEEDED")

    def test_undelegated_route_holds(self):
        memory = RecurrentFailureMemory()
        signal = failure()
        memory.observe(signal)
        result = memory.recommend(signal, delegated_actions=[], candidate_actions=["SET_PREVIEW_ENV"])
        self.assertEqual(result["reason"], "NO_DELEGATED_RECOVERY_ROUTE")

    def test_advisory_only_authority_invariants(self):
        memory = RecurrentFailureMemory()
        signal = failure()
        memory.observe(signal)
        result = memory.recommend(signal, delegated_actions=["X"], candidate_actions=["X"])
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["execution_authority"], "NONE")
        self.assertEqual(result["production_authority"], "HUMAN_ONLY")
        self.assertEqual(result["autonomous_ceiling"], "PREPARE_PR")


if __name__ == "__main__":
    unittest.main()
