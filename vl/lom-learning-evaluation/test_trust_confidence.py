import unittest

from trust_confidence import (
    CalibrationSample,
    TrustCalibrationEngine,
    TrustSignal,
    calibration_report,
)


def good_history(n=10, confidence=0.9, wrong_indexes=(0,), source="source-a", model="model-a"):
    wrong = set(wrong_indexes)
    return [
        CalibrationSample(
            sample_id=f"s{i}",
            source_id=source,
            model_id=model,
            asserted_confidence=confidence,
            outcome_correct=i not in wrong,
        )
        for i in range(n)
    ]


def good_signal(**overrides):
    data = dict(
        decision_id="d1",
        source_id="source-a",
        model_id="model-a",
        asserted_confidence=0.90,
        evidence_quality=0.92,
        source_reliability=0.95,
        model_reliability=0.95,
        disagreement=0.05,
        safety_pass=True,
        evidence_fresh=True,
        independent_validation=True,
        authority_valid=True,
    )
    data.update(overrides)
    return TrustSignal(**data)


class TrustConfidenceTests(unittest.TestCase):
    def test_well_calibrated_signal_is_trusted(self):
        result = TrustCalibrationEngine().assess(good_signal(), good_history())
        self.assertEqual(result.disposition, "TRUSTED")
        self.assertIn("CALIBRATED_TRUST_THRESHOLD_MET", result.reasons)
        self.assertTrue(result.production_locked)
        self.assertEqual(result.execution_authority, "NONE")
        self.assertEqual(result.autonomous_ceiling, "PREPARE_PR")
        self.assertEqual(result.authority_effect, "NONE")

    def test_insufficient_history_requires_review(self):
        result = TrustCalibrationEngine().assess(
            good_signal(), good_history(n=2, wrong_indexes=())
        )
        self.assertEqual(result.disposition, "REVIEW")
        self.assertIn("CALIBRATION_HISTORY_INSUFFICIENT", result.reasons)

    def test_stale_evidence_holds(self):
        result = TrustCalibrationEngine().assess(
            good_signal(evidence_fresh=False), good_history()
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("STALE_EVIDENCE", result.reasons)

    def test_missing_independent_validation_holds(self):
        result = TrustCalibrationEngine().assess(
            good_signal(independent_validation=False), good_history()
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("INDEPENDENT_VALIDATION_REQUIRED", result.reasons)

    def test_invalid_authority_holds(self):
        result = TrustCalibrationEngine().assess(
            good_signal(authority_valid=False), good_history()
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("AUTHORITY_INVALID", result.reasons)

    def test_safety_failure_holds(self):
        result = TrustCalibrationEngine().assess(
            good_signal(safety_pass=False), good_history()
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("SAFETY_NOT_VERIFIED", result.reasons)

    def test_low_evidence_quality_holds(self):
        result = TrustCalibrationEngine().assess(
            good_signal(evidence_quality=0.49), good_history()
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("EVIDENCE_QUALITY_TOO_LOW", result.reasons)

    def test_high_disagreement_holds(self):
        result = TrustCalibrationEngine().assess(
            good_signal(disagreement=0.8), good_history()
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("AGENT_DISAGREEMENT_HIGH", result.reasons)

    def test_medium_disagreement_requires_review(self):
        result = TrustCalibrationEngine().assess(
            good_signal(disagreement=0.4), good_history()
        )
        self.assertEqual(result.disposition, "REVIEW")
        self.assertIn("AGENT_DISAGREEMENT_REVIEW", result.reasons)

    def test_overconfident_history_is_not_trusted(self):
        history = good_history(
            n=10, confidence=0.95, wrong_indexes=(0, 1, 2, 3, 4, 5, 6)
        )
        result = TrustCalibrationEngine().assess(
            good_signal(asserted_confidence=0.95), history
        )
        self.assertNotEqual(result.disposition, "TRUSTED")
        self.assertIn("CALIBRATION_ERROR_HIGH", result.reasons)

    def test_source_reliability_empirically_capped(self):
        history = good_history(
            n=10, confidence=0.7, wrong_indexes=(0, 1, 2, 3, 4, 5, 6, 7)
        )
        result = TrustCalibrationEngine().assess(
            good_signal(source_reliability=0.99, model_id="other-model"),
            history,
        )
        self.assertLessEqual(result.effective_source_reliability, 0.2)
        self.assertIn("SOURCE_RELIABILITY_TOO_LOW", result.reasons)

    def test_model_reliability_empirically_capped(self):
        history = good_history(
            n=10, confidence=0.7, wrong_indexes=(0, 1, 2, 3, 4, 5, 6, 7)
        )
        result = TrustCalibrationEngine().assess(
            good_signal(model_reliability=0.99, source_id="other-source"),
            history,
        )
        self.assertLessEqual(result.effective_model_reliability, 0.2)
        self.assertIn("MODEL_RELIABILITY_TOO_LOW", result.reasons)

    def test_calibration_report_metrics(self):
        report = calibration_report(good_history())
        self.assertEqual(report.sample_count, 10)
        self.assertEqual(report.status, "READY")
        self.assertGreaterEqual(report.brier_score, 0)
        self.assertLessEqual(report.brier_score, 1)
        self.assertGreaterEqual(report.expected_calibration_error, 0)
        self.assertLessEqual(report.expected_calibration_error, 1)

    def test_empty_history_is_insufficient(self):
        report = calibration_report([])
        self.assertEqual(report.status, "INSUFFICIENT")
        self.assertEqual(report.sample_count, 0)

    def test_fingerprint_is_deterministic(self):
        engine = TrustCalibrationEngine()
        a = engine.assess(good_signal(), good_history())
        b = engine.assess(good_signal(), good_history())
        self.assertEqual(a.fingerprint, b.fingerprint)

    def test_confidence_out_of_range_rejected(self):
        with self.assertRaisesRegex(
            ValueError, "ASSERTED_CONFIDENCE_OUT_OF_RANGE"
        ):
            TrustCalibrationEngine().assess(
                good_signal(asserted_confidence=1.1), good_history()
            )

    def test_non_boolean_safety_rejected(self):
        with self.assertRaisesRegex(ValueError, "SAFETY_PASS_BOOL_REQUIRED"):
            TrustCalibrationEngine().assess(
                good_signal(safety_pass=1), good_history()
            )

    def test_bad_calibration_bins_rejected(self):
        with self.assertRaisesRegex(ValueError, "CALIBRATION_BINS_TOO_SMALL"):
            calibration_report(good_history(), bins=1)


if __name__ == "__main__":
    unittest.main()
