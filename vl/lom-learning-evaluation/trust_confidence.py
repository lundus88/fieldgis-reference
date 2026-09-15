from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Iterable, List, Tuple


def _score(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name}_NOT_NUMERIC")
    value = float(value)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"{name}_OUT_OF_RANGE")
    return value


@dataclass(frozen=True)
class CalibrationSample:
    sample_id: str
    source_id: str
    model_id: str
    asserted_confidence: float
    outcome_correct: bool

    def validate(self) -> None:
        for field_name in ("sample_id", "source_id", "model_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name.upper()}_REQUIRED")
        _score("ASSERTED_CONFIDENCE", self.asserted_confidence)
        if not isinstance(self.outcome_correct, bool):
            raise ValueError("OUTCOME_CORRECT_BOOL_REQUIRED")


@dataclass(frozen=True)
class TrustSignal:
    decision_id: str
    source_id: str
    model_id: str
    asserted_confidence: float
    evidence_quality: float
    source_reliability: float
    model_reliability: float
    disagreement: float
    safety_pass: bool
    evidence_fresh: bool
    independent_validation: bool
    authority_valid: bool

    def validate(self) -> None:
        for field_name in ("decision_id", "source_id", "model_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name.upper()}_REQUIRED")
        for field_name in (
            "asserted_confidence",
            "evidence_quality",
            "source_reliability",
            "model_reliability",
            "disagreement",
        ):
            _score(field_name.upper(), getattr(self, field_name))
        for field_name in (
            "safety_pass",
            "evidence_fresh",
            "independent_validation",
            "authority_valid",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name.upper()}_BOOL_REQUIRED")


@dataclass(frozen=True)
class CalibrationReport:
    sample_count: int
    empirical_accuracy: float
    brier_score: float
    expected_calibration_error: float
    overconfidence_gap: float
    status: str


@dataclass(frozen=True)
class TrustAssessment:
    decision_id: str
    calibrated_confidence: float
    trust_score: float
    disposition: str
    reasons: Tuple[str, ...]
    calibration: CalibrationReport
    effective_source_reliability: float
    effective_model_reliability: float
    production_locked: bool
    execution_authority: str
    autonomous_ceiling: str
    authority_effect: str
    fingerprint: str


def calibration_report(samples: Iterable[CalibrationSample], bins: int = 5) -> CalibrationReport:
    values = list(samples)
    if bins < 2:
        raise ValueError("CALIBRATION_BINS_TOO_SMALL")
    for sample in values:
        sample.validate()
    if not values:
        return CalibrationReport(0, 0.0, 1.0, 1.0, 1.0, "INSUFFICIENT")

    n = len(values)
    outcomes = [1.0 if item.outcome_correct else 0.0 for item in values]
    confidences = [float(item.asserted_confidence) for item in values]
    empirical_accuracy = sum(outcomes) / n
    brier = sum((c - y) ** 2 for c, y in zip(confidences, outcomes)) / n

    bucketed: List[List[Tuple[float, float]]] = [[] for _ in range(bins)]
    for confidence, outcome in zip(confidences, outcomes):
        idx = min(bins - 1, int(confidence * bins))
        bucketed[idx].append((confidence, outcome))

    ece = 0.0
    for bucket in bucketed:
        if not bucket:
            continue
        avg_conf = sum(item[0] for item in bucket) / len(bucket)
        avg_outcome = sum(item[1] for item in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(avg_conf - avg_outcome)

    avg_confidence = sum(confidences) / n
    overconfidence_gap = max(0.0, avg_confidence - empirical_accuracy)
    status = "READY" if n >= 6 else "INSUFFICIENT"

    return CalibrationReport(
        sample_count=n,
        empirical_accuracy=round(empirical_accuracy, 4),
        brier_score=round(brier, 4),
        expected_calibration_error=round(ece, 4),
        overconfidence_gap=round(overconfidence_gap, 4),
        status=status,
    )


def _historical_accuracy(samples: List[CalibrationSample], attr: str, value: str) -> Tuple[int, float]:
    selected = [item for item in samples if getattr(item, attr) == value]
    if not selected:
        return 0, 0.0
    return len(selected), sum(1.0 if item.outcome_correct else 0.0 for item in selected) / len(selected)


def _assessment_fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


class TrustCalibrationEngine:
    MIN_HISTORY = 6

    def assess(self, signal: TrustSignal, history: Iterable[CalibrationSample]) -> TrustAssessment:
        signal.validate()
        samples = list(history)
        for sample in samples:
            sample.validate()

        relevant = [
            sample for sample in samples
            if sample.source_id == signal.source_id or sample.model_id == signal.model_id
        ]
        report = calibration_report(relevant)

        source_n, source_accuracy = _historical_accuracy(samples, "source_id", signal.source_id)
        model_n, model_accuracy = _historical_accuracy(samples, "model_id", signal.model_id)

        effective_source = float(signal.source_reliability)
        if source_n >= 3:
            effective_source = min(effective_source, source_accuracy)
        effective_model = float(signal.model_reliability)
        if model_n >= 3:
            effective_model = min(effective_model, model_accuracy)

        hard_reasons: List[str] = []
        if not signal.authority_valid:
            hard_reasons.append("AUTHORITY_INVALID")
        if not signal.safety_pass:
            hard_reasons.append("SAFETY_NOT_VERIFIED")
        if not signal.evidence_fresh:
            hard_reasons.append("STALE_EVIDENCE")
        if not signal.independent_validation:
            hard_reasons.append("INDEPENDENT_VALIDATION_REQUIRED")
        if signal.evidence_quality < 0.50:
            hard_reasons.append("EVIDENCE_QUALITY_TOO_LOW")
        if signal.disagreement > 0.65:
            hard_reasons.append("AGENT_DISAGREEMENT_HIGH")
        if effective_source < 0.40:
            hard_reasons.append("SOURCE_RELIABILITY_TOO_LOW")
        if effective_model < 0.40:
            hard_reasons.append("MODEL_RELIABILITY_TOO_LOW")

        if report.sample_count:
            alpha = min(0.80, report.sample_count / (report.sample_count + 5.0))
            calibrated = (
                (1.0 - alpha) * float(signal.asserted_confidence)
                + alpha * report.empirical_accuracy
                - 0.25 * report.overconfidence_gap
            )
        else:
            calibrated = 0.5 * float(signal.asserted_confidence)
        calibrated = max(0.0, min(1.0, calibrated))

        calibration_quality = max(
            0.0, 1.0 - min(1.0, report.expected_calibration_error / 0.25)
        )
        trust_score = (
            0.35 * calibrated
            + 0.20 * float(signal.evidence_quality)
            + 0.15 * effective_source
            + 0.15 * effective_model
            + 0.10 * (1.0 - float(signal.disagreement))
            + 0.05 * calibration_quality
        )
        trust_score = max(0.0, min(1.0, trust_score))

        advisory_reasons: List[str] = []
        if report.status != "READY":
            advisory_reasons.append("CALIBRATION_HISTORY_INSUFFICIENT")
        if report.brier_score > 0.20 or report.expected_calibration_error > 0.15:
            advisory_reasons.append("CALIBRATION_ERROR_HIGH")
        if effective_source < 0.60:
            advisory_reasons.append("SOURCE_RELIABILITY_REVIEW")
        if effective_model < 0.60:
            advisory_reasons.append("MODEL_RELIABILITY_REVIEW")
        if signal.disagreement > 0.35:
            advisory_reasons.append("AGENT_DISAGREEMENT_REVIEW")

        reasons: List[str] = list(hard_reasons) + advisory_reasons
        if hard_reasons:
            disposition = "HOLD"
        else:
            trusted = (
                report.status == "READY"
                and report.brier_score <= 0.20
                and report.expected_calibration_error <= 0.15
                and calibrated >= 0.72
                and trust_score >= 0.78
                and signal.evidence_quality >= 0.75
                and effective_source >= 0.70
                and effective_model >= 0.70
                and signal.disagreement <= 0.25
            )
            if trusted:
                disposition = "TRUSTED"
                reasons.append("CALIBRATED_TRUST_THRESHOLD_MET")
            elif trust_score >= 0.55:
                disposition = "REVIEW"
                if not reasons:
                    reasons.append("TRUST_THRESHOLD_NOT_MET")
            else:
                disposition = "HOLD"
                if not reasons:
                    reasons.append("TRUST_SCORE_TOO_LOW")

        base_payload = {
            "signal": asdict(signal),
            "calibration": asdict(report),
            "effective_source_reliability": round(effective_source, 4),
            "effective_model_reliability": round(effective_model, 4),
            "calibrated_confidence": round(calibrated, 4),
            "trust_score": round(trust_score, 4),
            "disposition": disposition,
            "reasons": tuple(sorted(set(reasons))),
            "production_locked": True,
            "execution_authority": "NONE",
            "autonomous_ceiling": "PREPARE_PR",
            "authority_effect": "NONE",
        }
        fingerprint = _assessment_fingerprint(base_payload)

        return TrustAssessment(
            decision_id=signal.decision_id,
            calibrated_confidence=base_payload["calibrated_confidence"],
            trust_score=base_payload["trust_score"],
            disposition=disposition,
            reasons=base_payload["reasons"],
            calibration=report,
            effective_source_reliability=base_payload["effective_source_reliability"],
            effective_model_reliability=base_payload["effective_model_reliability"],
            production_locked=True,
            execution_authority="NONE",
            autonomous_ceiling="PREPARE_PR",
            authority_effect="NONE",
            fingerprint=fingerprint,
        )


if __name__ == "__main__":
    history = [
        CalibrationSample(f"s{i}", "trusted-source", "trusted-model", 0.90, i != 0)
        for i in range(10)
    ]
    signal = TrustSignal(
        decision_id="example",
        source_id="trusted-source",
        model_id="trusted-model",
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
    result = TrustCalibrationEngine().assess(signal, history)
    print(json.dumps(asdict(result), sort_keys=True))
