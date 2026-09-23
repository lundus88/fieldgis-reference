from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import secrets
import time
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

HUMAN_ONLY_TARGETS = {
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_RELEASE",
    "PRODUCTION_DATA_MUTATION",
    "AUTHORITY_WIDENING",
    "AUTH_SECURITY_POLICY_CHANGE",
    "CUSTOMER_COMMITMENT",
    "BID_SUBMISSION",
    "PRICING_COMMITMENT",
    "CONTRACT_COMMITMENT",
    "FINANCIAL_COMMITMENT",
    "DATA_DELETION",
}

ALLOWED_TARGETS = {
    "PROMPT",
    "ROUTING",
    "DOCUMENTATION",
    "TEST_COVERAGE",
    "NON_PROD_CODE",
    "NON_PROD_WORKFLOW",
    "UI_NON_PROD",
    "EVALUATION",
    "OBSERVABILITY",
}

EVIDENCE_KINDS = {
    "QUALIFICATION",
    "TRIGGER",
    "EVALUATION",
    "BASELINE",
    "USAGE",
    "CERTIFICATION",
}

TASK_STATES = (
    "DISCOVERED",
    "QUALIFIED",
    "PLANNED",
    "SANDBOX",
    "TESTED",
    "SCORED",
    "REMEDIATED",
    "CERTIFIED",
    "PREPARE_PR",
    "HOLD",
    "REJECT",
    "ESCALATE",
)

TRIGGER_TYPES = {"MANUAL", "SCHEDULE", "EVENT", "CI_FAILURE", "OBSERVABILITY_ALERT"}
TERMINAL_STATES = {"PREPARE_PR", "HOLD", "REJECT", "ESCALATE"}

ALLOWED_TRANSITIONS = {
    "DISCOVERED": {"QUALIFIED", "HOLD", "ESCALATE"},
    "QUALIFIED": {"PLANNED", "HOLD"},
    "PLANNED": {"SANDBOX", "HOLD"},
    "SANDBOX": {"TESTED", "REMEDIATED", "HOLD", "REJECT"},
    "REMEDIATED": {"TESTED", "REMEDIATED", "HOLD", "REJECT"},
    "TESTED": {"SCORED", "HOLD", "REJECT"},
    "SCORED": {"CERTIFIED", "HOLD"},
    "CERTIFIED": {"PREPARE_PR", "HOLD"},
}

HEX_DIGEST_LEN = 64


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_payload(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _valid_digest(value: str) -> bool:
    if len(value) != HEX_DIGEST_LEN:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value != ("0" * HEX_DIGEST_LEN)


def _valid_ref(value: str) -> bool:
    value = value.strip()
    return bool(value) and ("://" in value or value.startswith(("urn:", "sha256:")))


@dataclass(frozen=True)
class Budget:
    max_cost_usd: float
    max_elapsed_seconds: int
    max_retries: int
    max_tool_calls: int

    def valid(self) -> bool:
        return (
            self.max_cost_usd >= 0
            and self.max_elapsed_seconds > 0
            and self.max_retries >= 0
            and self.max_tool_calls > 0
        )


@dataclass(frozen=True)
class Usage:
    cost_usd: float
    elapsed_seconds: int
    retries: int
    tool_calls: int

    def valid(self) -> bool:
        return (
            self.cost_usd >= 0
            and self.elapsed_seconds >= 0
            and self.retries >= 0
            and self.tool_calls >= 0
        )

    def within(self, budget: Budget) -> bool:
        return (
            self.valid()
            and self.cost_usd <= budget.max_cost_usd
            and self.elapsed_seconds <= budget.max_elapsed_seconds
            and self.retries <= budget.max_retries
            and self.tool_calls <= budget.max_tool_calls
        )


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    kind: str
    issuer: str
    subject_ref: str
    provenance_ref: str
    issued_at: int
    expires_at: int
    payload_digest: str
    signature: str

    def unsigned_payload(self) -> Dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "issuer": self.issuer,
            "subject_ref": self.subject_ref,
            "provenance_ref": self.provenance_ref,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "payload_digest": self.payload_digest,
        }

    @classmethod
    def sign(
        cls,
        *,
        key: bytes,
        evidence_id: str,
        kind: str,
        issuer: str,
        subject_ref: str,
        provenance_ref: str,
        issued_at: int,
        expires_at: int,
        payload_digest: str,
    ) -> "EvidenceRecord":
        unsigned = {
            "evidence_id": evidence_id,
            "kind": kind,
            "issuer": issuer,
            "subject_ref": subject_ref,
            "provenance_ref": provenance_ref,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "payload_digest": payload_digest,
        }
        signature = hmac.new(
            key,
            _canonical_json(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return cls(signature=signature, **unsigned)

    def verify(
        self,
        *,
        key: bytes,
        now: int,
        max_age_seconds: int,
        expected_kind: Optional[str] = None,
        expected_subject_ref: Optional[str] = None,
        expected_issuer: Optional[str] = None,
        clock_skew_seconds: int = 60,
    ) -> bool:
        if (
            not self.evidence_id.strip()
            or self.kind not in EVIDENCE_KINDS
            or not self.issuer.strip()
            or not _valid_ref(self.subject_ref)
            or not _valid_ref(self.provenance_ref)
            or not _valid_digest(self.payload_digest)
            or not _valid_digest(self.signature)
        ):
            return False
        if expected_kind is not None and self.kind != expected_kind:
            return False
        if expected_subject_ref is not None and self.subject_ref != expected_subject_ref:
            return False
        if expected_issuer is not None and self.issuer != expected_issuer:
            return False
        if self.expires_at <= self.issued_at:
            return False
        if self.issued_at > now + clock_skew_seconds:
            return False
        if now > self.expires_at:
            return False
        if now - self.issued_at > max_age_seconds:
            return False

        expected_signature = hmac.new(
            key,
            _canonical_json(self.unsigned_payload()).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected_signature)


@dataclass(frozen=True)
class Trigger:
    trigger_id: str
    trigger_type: str
    source_ref: str
    evidence: EvidenceRecord

    def basic_valid(self) -> bool:
        return (
            bool(self.trigger_id.strip())
            and self.trigger_type in TRIGGER_TYPES
            and _valid_ref(self.source_ref)
        )


@dataclass(frozen=True)
class Evaluation:
    correctness: float
    safety: float
    regression: float
    ux: float = 1.0
    performance: float = 1.0

    def values(self) -> Tuple[float, ...]:
        return (
            self.correctness,
            self.safety,
            self.regression,
            self.ux,
            self.performance,
        )

    def valid(self) -> bool:
        return all(0.0 <= value <= 1.0 for value in self.values())

    def weighted_score(self) -> float:
        return round(
            (0.35 * self.correctness)
            + (0.30 * self.safety)
            + (0.20 * self.regression)
            + (0.075 * self.ux)
            + (0.075 * self.performance),
            4,
        )

    def payload(self) -> Dict[str, float]:
        return {
            "correctness": self.correctness,
            "safety": self.safety,
            "regression": self.regression,
            "ux": self.ux,
            "performance": self.performance,
        }


@dataclass(frozen=True)
class CertificationEvidence:
    certifier_id: str
    independent_validation: bool
    evidence_consistent: bool
    evidence: EvidenceRecord


@dataclass(frozen=True)
class TransitionRecord:
    sequence: int
    from_state: str
    to_state: str
    reason: str
    previous_digest: str
    digest: str


@dataclass
class ImprovementTask:
    task_id: str
    target: str
    risk: str
    reversible: bool
    production: bool
    objective: str
    builder_id: str
    certifier_id: str
    budget: Budget
    qualification_evidence: EvidenceRecord
    trigger: Trigger
    _state: str = field(default="DISCOVERED", init=False, repr=False)
    _reason: str = field(default="CREATED", init=False, repr=False)
    _attempts: int = field(default=0, init=False, repr=False)
    _ledger: List[TransitionRecord] = field(default_factory=list, init=False, repr=False)

    @property
    def state(self) -> str:
        return self._state

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def history(self) -> Tuple[str, ...]:
        return tuple(["DISCOVERED"] + [record.to_state for record in self._ledger])

    @property
    def ledger(self) -> Tuple[TransitionRecord, ...]:
        return tuple(self._ledger)


class CAIE:
    """Bounded Continuous Autonomous Improvement Engine.

    P0.1 hardening adds signed/fresh evidence and a tamper-evident transition ledger.
    Autonomous ceiling: PREPARE_PR.
    Protected-main merge and Production remain HUMAN_ONLY.
    """

    def __init__(
        self,
        *,
        evidence_keys: Mapping[str, bytes],
        min_correctness: float = 0.90,
        min_safety: float = 0.95,
        min_regression: float = 0.95,
        min_total_score: float = 0.92,
        max_remediation_attempts: int = 2,
        max_evidence_age_seconds: int = 3600,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        if not evidence_keys:
            raise ValueError("EVIDENCE_KEYS_REQUIRED")
        normalized_keys: Dict[str, bytes] = {}
        for issuer, key in evidence_keys.items():
            if not issuer.strip():
                raise ValueError("EVIDENCE_ISSUER_REQUIRED")
            if not isinstance(key, (bytes, bytearray)) or len(key) < 16:
                raise ValueError("EVIDENCE_KEY_TOO_SHORT")
            normalized_keys[issuer] = bytes(key)
        if max_remediation_attempts < 0:
            raise ValueError("INVALID_REMEDIATION_LIMIT")
        if max_evidence_age_seconds <= 0:
            raise ValueError("INVALID_EVIDENCE_AGE")
        for threshold in (
            min_correctness,
            min_safety,
            min_regression,
            min_total_score,
        ):
            if threshold < 0 or threshold > 1:
                raise ValueError("INVALID_QUALITY_THRESHOLD")

        self.__evidence_keys = normalized_keys
        self.__transition_key = secrets.token_bytes(32)
        self.__certification_tokens: Dict[int, str] = {}
        self.min_correctness = min_correctness
        self.min_safety = min_safety
        self.min_regression = min_regression
        self.min_total_score = min_total_score
        self.max_remediation_attempts = max_remediation_attempts
        self.max_evidence_age_seconds = max_evidence_age_seconds
        self.now_fn = now_fn

    def _now(self) -> int:
        return int(self.now_fn())

    def _verify_evidence(
        self,
        evidence: EvidenceRecord,
        *,
        kind: str,
        subject_ref: str,
        issuer: Optional[str] = None,
    ) -> bool:
        key = self.__evidence_keys.get(evidence.issuer)
        if key is None:
            return False
        return evidence.verify(
            key=key,
            now=self._now(),
            max_age_seconds=self.max_evidence_age_seconds,
            expected_kind=kind,
            expected_subject_ref=subject_ref,
            expected_issuer=issuer,
        )

    @staticmethod
    def _task_policy_digest(task: ImprovementTask) -> str:
        return digest_payload(
            {
                "task_id": task.task_id,
                "target": task.target,
                "risk": task.risk,
                "reversible": task.reversible,
                "production": task.production,
                "objective": task.objective,
                "builder_id": task.builder_id,
                "certifier_id": task.certifier_id,
                "budget": {
                    "max_cost_usd": task.budget.max_cost_usd,
                    "max_elapsed_seconds": task.budget.max_elapsed_seconds,
                    "max_retries": task.budget.max_retries,
                    "max_tool_calls": task.budget.max_tool_calls,
                },
                "qualification_evidence_signature": task.qualification_evidence.signature,
                "trigger": {
                    "trigger_id": task.trigger.trigger_id,
                    "trigger_type": task.trigger.trigger_type,
                    "source_ref": task.trigger.source_ref,
                    "evidence_signature": task.trigger.evidence.signature,
                },
            }
        )

    def _transition_digest(
        self,
        task: ImprovementTask,
        *,
        sequence: int,
        from_state: str,
        to_state: str,
        reason: str,
        previous_digest: str,
    ) -> str:
        payload = {
            "task_id": task.task_id,
            "sequence": sequence,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "previous_digest": previous_digest,
            "task_policy_digest": self._task_policy_digest(task),
        }
        return hmac.new(
            self.__transition_key,
            _canonical_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _transition(self, task: ImprovementTask, new_state: str, reason: str) -> str:
        current = task._state
        if current in TERMINAL_STATES:
            return current
        if new_state not in ALLOWED_TRANSITIONS.get(current, set()):
            raise ValueError("ILLEGAL_STATE_TRANSITION")
        previous_digest = task._ledger[-1].digest if task._ledger else ("0" * HEX_DIGEST_LEN)
        sequence = len(task._ledger) + 1
        digest = self._transition_digest(
            task,
            sequence=sequence,
            from_state=current,
            to_state=new_state,
            reason=reason,
            previous_digest=previous_digest,
        )
        task._ledger.append(
            TransitionRecord(
                sequence=sequence,
                from_state=current,
                to_state=new_state,
                reason=reason,
                previous_digest=previous_digest,
                digest=digest,
            )
        )
        task._state = new_state
        task._reason = reason
        return task._state

    def _fail_closed(self, task: ImprovementTask, disposition: str, reason: str) -> str:
        if task.state in TERMINAL_STATES:
            return task.state
        return self._transition(task, disposition, reason)

    def _ledger_valid(self, task: ImprovementTask) -> bool:
        previous_state = "DISCOVERED"
        previous_digest = "0" * HEX_DIGEST_LEN
        for expected_sequence, record in enumerate(task._ledger, start=1):
            if record.sequence != expected_sequence:
                return False
            if record.from_state != previous_state:
                return False
            if record.to_state not in ALLOWED_TRANSITIONS.get(previous_state, set()):
                return False
            if record.previous_digest != previous_digest:
                return False
            expected_digest = self._transition_digest(
                task,
                sequence=record.sequence,
                from_state=record.from_state,
                to_state=record.to_state,
                reason=record.reason,
                previous_digest=record.previous_digest,
            )
            if not hmac.compare_digest(record.digest, expected_digest):
                return False
            previous_state = record.to_state
            previous_digest = record.digest
        return task._state == previous_state

    @staticmethod
    def _valid_success_history(history: Sequence[str]) -> bool:
        if len(history) < 7 or history[0] != "DISCOVERED":
            return False
        index = 1
        for required in ("QUALIFIED", "PLANNED", "SANDBOX"):
            if index >= len(history) or history[index] != required:
                return False
            index += 1
        while index < len(history) and history[index] == "REMEDIATED":
            index += 1
        for required in ("TESTED", "SCORED", "CERTIFIED"):
            if index >= len(history) or history[index] != required:
                return False
            index += 1
        return index == len(history)

    def qualify(self, task: ImprovementTask) -> str:
        subject = f"urn:lom:task:{task.task_id}"
        if task.state != "DISCOVERED":
            return self._fail_closed(task, "HOLD", "QUALIFY_REQUIRES_DISCOVERED")
        if not task.task_id.strip() or not task.objective.strip():
            return self._transition(task, "HOLD", "IDENTITY_OR_OBJECTIVE_REQUIRED")
        if not self._verify_evidence(
            task.qualification_evidence,
            kind="QUALIFICATION",
            subject_ref=subject,
        ):
            return self._transition(task, "HOLD", "QUALIFICATION_EVIDENCE_INVALID")
        qualification_payload = {
            "task_id": task.task_id,
            "target": task.target,
            "risk": task.risk,
            "reversible": task.reversible,
            "production": task.production,
            "objective": task.objective,
            "builder_id": task.builder_id,
            "certifier_id": task.certifier_id,
        }
        if task.qualification_evidence.payload_digest != digest_payload(qualification_payload):
            return self._transition(task, "HOLD", "QUALIFICATION_DIGEST_MISMATCH")
        if not task.trigger.basic_valid():
            return self._transition(task, "HOLD", "TRIGGER_INVALID")
        if not self._verify_evidence(
            task.trigger.evidence,
            kind="TRIGGER",
            subject_ref=subject,
        ):
            return self._transition(task, "HOLD", "TRIGGER_EVIDENCE_INVALID")
        trigger_payload = {
            "trigger_id": task.trigger.trigger_id,
            "trigger_type": task.trigger.trigger_type,
            "source_ref": task.trigger.source_ref,
        }
        if task.trigger.evidence.payload_digest != digest_payload(trigger_payload):
            return self._transition(task, "HOLD", "TRIGGER_DIGEST_MISMATCH")
        if not task.budget.valid():
            return self._transition(task, "HOLD", "BUDGET_INVALID")
        if task.target in HUMAN_ONLY_TARGETS:
            return self._transition(task, "ESCALATE", "HUMAN_ONLY_TARGET")
        if task.target not in ALLOWED_TARGETS:
            return self._transition(task, "HOLD", "UNKNOWN_TARGET")
        if task.production:
            return self._transition(task, "ESCALATE", "PRODUCTION_BOUNDARY")
        if task.risk not in {"LOW", "MEDIUM", "HIGH"}:
            return self._transition(task, "HOLD", "UNKNOWN_RISK")
        if task.risk == "HIGH":
            return self._transition(task, "ESCALATE", "HIGH_RISK")
        if not task.reversible:
            return self._transition(task, "HOLD", "REVERSIBILITY_REQUIRED")
        if not task.builder_id.strip() or not task.certifier_id.strip():
            return self._transition(task, "HOLD", "ROLE_IDENTITY_REQUIRED")
        if task.builder_id == task.certifier_id:
            return self._transition(task, "HOLD", "BUILDER_SELF_CERTIFICATION_FORBIDDEN")
        return self._transition(task, "QUALIFIED", "BOUNDARY_AND_EVIDENCE_CHECKS_PASSED")

    def plan(self, task: ImprovementTask) -> str:
        if task.state != "QUALIFIED":
            return self._fail_closed(task, "HOLD", "PLAN_REQUIRES_QUALIFIED")
        return self._transition(task, "PLANNED", "BOUNDED_PLAN_READY")

    def enter_sandbox(self, task: ImprovementTask, isolated: bool) -> str:
        if task.state != "PLANNED":
            return self._fail_closed(task, "HOLD", "SANDBOX_REQUIRES_PLANNED")
        if not isolated:
            return self._transition(task, "HOLD", "ISOLATED_EXECUTION_REQUIRED")
        return self._transition(task, "SANDBOX", "ISOLATED_EXECUTION_CONFIRMED")

    def record_test(self, task: ImprovementTask, tests_passed: bool) -> str:
        if task.state not in {"SANDBOX", "REMEDIATED"}:
            return self._fail_closed(task, "HOLD", "TEST_REQUIRES_SANDBOX_OR_REMEDIATED")
        if not tests_passed:
            if task._attempts < self.max_remediation_attempts:
                task._attempts += 1
                return self._transition(task, "REMEDIATED", "TEST_FAILED_REMEDIATE")
            return self._transition(task, "REJECT", "TEST_FAILED_REMEDIATION_EXHAUSTED")
        return self._transition(task, "TESTED", "DETERMINISTIC_TESTS_PASSED")

    def score(
        self,
        task: ImprovementTask,
        *,
        evaluation: Evaluation,
        evaluation_evidence: EvidenceRecord,
        baseline: Optional[Evaluation],
        baseline_evidence: Optional[EvidenceRecord],
        usage: Usage,
        usage_evidence: EvidenceRecord,
    ) -> str:
        subject = f"urn:lom:task:{task.task_id}"
        if task.state != "TESTED":
            return self._fail_closed(task, "HOLD", "SCORING_REQUIRES_TESTED")
        if not evaluation.valid():
            return self._transition(task, "HOLD", "EVALUATION_SCORE_INVALID")
        if not self._verify_evidence(
            evaluation_evidence,
            kind="EVALUATION",
            subject_ref=subject,
        ):
            return self._transition(task, "HOLD", "EVALUATION_EVIDENCE_INVALID")
        if evaluation_evidence.payload_digest != digest_payload(evaluation.payload()):
            return self._transition(task, "HOLD", "EVALUATION_DIGEST_MISMATCH")
        if not usage.valid():
            return self._transition(task, "HOLD", "USAGE_EVIDENCE_INVALID")
        if not self._verify_evidence(
            usage_evidence,
            kind="USAGE",
            subject_ref=subject,
        ):
            return self._transition(task, "HOLD", "USAGE_EVIDENCE_INVALID")
        if usage_evidence.payload_digest != digest_payload(
            {
                "cost_usd": usage.cost_usd,
                "elapsed_seconds": usage.elapsed_seconds,
                "retries": usage.retries,
                "tool_calls": usage.tool_calls,
            }
        ):
            return self._transition(task, "HOLD", "USAGE_DIGEST_MISMATCH")
        if not usage.within(task.budget):
            return self._transition(task, "REJECT", "BUDGET_OVERRUN")
        if baseline is None or baseline_evidence is None:
            return self._transition(task, "HOLD", "BASELINE_EVIDENCE_REQUIRED")
        if not baseline.valid():
            return self._transition(task, "HOLD", "BASELINE_SCORE_INVALID")
        if not self._verify_evidence(
            baseline_evidence,
            kind="BASELINE",
            subject_ref=subject,
        ):
            return self._transition(task, "HOLD", "BASELINE_EVIDENCE_INVALID")
        if baseline_evidence.payload_digest != digest_payload(baseline.payload()):
            return self._transition(task, "HOLD", "BASELINE_DIGEST_MISMATCH")
        if (
            evaluation.correctness < baseline.correctness
            or evaluation.safety < baseline.safety
            or evaluation.regression < baseline.regression
        ):
            return self._transition(task, "REJECT", "QUALITY_REGRESSION")
        if evaluation.correctness < self.min_correctness:
            return self._transition(task, "REJECT", "CORRECTNESS_BELOW_THRESHOLD")
        if evaluation.safety < self.min_safety:
            return self._transition(task, "REJECT", "SAFETY_BELOW_THRESHOLD")
        if evaluation.regression < self.min_regression:
            return self._transition(task, "REJECT", "REGRESSION_BELOW_THRESHOLD")
        if evaluation.weighted_score() < self.min_total_score:
            return self._transition(task, "REJECT", "TOTAL_SCORE_BELOW_THRESHOLD")
        return self._transition(task, "SCORED", "SIGNED_QUALITY_EVIDENCE_PASSED")

    def certify(self, task: ImprovementTask, certification: CertificationEvidence) -> str:
        subject = f"urn:lom:task:{task.task_id}"
        if task.state != "SCORED":
            return self._fail_closed(task, "HOLD", "CERTIFICATION_REQUIRES_SCORED")
        if certification.certifier_id != task.certifier_id:
            return self._transition(task, "HOLD", "CERTIFIER_IDENTITY_MISMATCH")
        if certification.certifier_id == task.builder_id:
            return self._transition(task, "HOLD", "BUILDER_SELF_CERTIFICATION_FORBIDDEN")
        if not certification.independent_validation:
            return self._transition(task, "HOLD", "INDEPENDENT_VALIDATION_REQUIRED")
        if not certification.evidence_consistent:
            return self._transition(task, "HOLD", "EVIDENCE_CONTRADICTION")
        if not self._verify_evidence(
            certification.evidence,
            kind="CERTIFICATION",
            subject_ref=subject,
            issuer=certification.certifier_id,
        ):
            return self._transition(task, "HOLD", "CERTIFICATION_EVIDENCE_INVALID")
        expected_digest = digest_payload(
            {
                "task_id": task.task_id,
                "certifier_id": certification.certifier_id,
                "independent_validation": certification.independent_validation,
                "evidence_consistent": certification.evidence_consistent,
                "scored_ledger_tail": task._ledger[-1].digest,
            }
        )
        if certification.evidence.payload_digest != expected_digest:
            return self._transition(task, "HOLD", "CERTIFICATION_DIGEST_MISMATCH")
        state = self._transition(task, "CERTIFIED", "INDEPENDENT_SIGNED_VALIDATION_PASSED")
        token_payload = {
            "task_id": task.task_id,
            "ledger_tail": task._ledger[-1].digest,
            "certifier_id": certification.certifier_id,
        }
        self.__certification_tokens[id(task)] = hmac.new(
            self.__transition_key,
            _canonical_json(token_payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return state

    def prepare_pr(self, task: ImprovementTask) -> str:
        if task.state != "CERTIFIED":
            return self._fail_closed(task, "HOLD", "PREPARE_PR_REQUIRES_CERTIFIED")
        if not self._ledger_valid(task):
            task._state = "HOLD"
            task._reason = "TRANSITION_LEDGER_INVALID"
            return task.state
        if not self._valid_success_history(task.history):
            return self._transition(task, "HOLD", "CERTIFICATION_LINEAGE_INCOMPLETE")
        expected_token = self.__certification_tokens.get(id(task))
        if not expected_token:
            return self._transition(task, "HOLD", "CERTIFICATION_TOKEN_REQUIRED")
        token_payload = {
            "task_id": task.task_id,
            "ledger_tail": task._ledger[-1].digest,
            "certifier_id": task.certifier_id,
        }
        actual_token = hmac.new(
            self.__transition_key,
            _canonical_json(token_payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_token, actual_token):
            return self._transition(task, "HOLD", "CERTIFICATION_TOKEN_INVALID")
        return self._transition(task, "PREPARE_PR", "AUTONOMOUS_CEILING_REACHED")

    def merge_protected_main(self) -> None:
        raise PermissionError("HUMAN_APPROVAL_REQUIRED")

    def deploy_production(self) -> None:
        raise PermissionError("HUMAN_APPROVAL_REQUIRED")


def run_to_prepare_pr(
    *,
    evidence_keys: Mapping[str, bytes],
    task: ImprovementTask,
    evaluation: Evaluation,
    evaluation_evidence: EvidenceRecord,
    baseline: Evaluation,
    baseline_evidence: EvidenceRecord,
    usage: Usage,
    usage_evidence: EvidenceRecord,
    certification_factory: Callable[[ImprovementTask], CertificationEvidence],
    tests_passed: bool = True,
    isolated: bool = True,
    now_fn: Callable[[], float] = time.time,
) -> ImprovementTask:
    engine = CAIE(evidence_keys=evidence_keys, now_fn=now_fn)
    if engine.qualify(task) != "QUALIFIED":
        return task
    if engine.plan(task) != "PLANNED":
        return task
    if engine.enter_sandbox(task, isolated=isolated) != "SANDBOX":
        return task
    if engine.record_test(task, tests_passed=tests_passed) != "TESTED":
        return task
    if engine.score(
        task,
        evaluation=evaluation,
        evaluation_evidence=evaluation_evidence,
        baseline=baseline,
        baseline_evidence=baseline_evidence,
        usage=usage,
        usage_evidence=usage_evidence,
    ) != "SCORED":
        return task
    certification = certification_factory(task)
    if engine.certify(task, certification) != "CERTIFIED":
        return task
    engine.prepare_pr(task)
    return task
