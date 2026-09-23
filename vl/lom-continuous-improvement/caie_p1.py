from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import time
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Tuple

AUTONOMOUS_CEILING = "PREPARE_PR"

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

EVENT_TYPES = {"MANUAL", "SCHEDULE", "EVENT", "CI_FAILURE", "OBSERVABILITY_ALERT"}
RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}
TERMINAL_STATES = {"PREPARE_PR", "HOLD", "REJECT", "ESCALATE"}

BOARD_TRANSITIONS = {
    "QUEUED": {"ACTIVE", "HOLD", "ESCALATE"},
    "ACTIVE": {"VERIFYING", "HOLD", "REJECT", "ESCALATE"},
    "VERIFYING": {"REMEDIATING", "SCORED", "HOLD", "REJECT", "ESCALATE"},
    "REMEDIATING": {"VERIFYING", "HOLD", "REJECT", "ESCALATE"},
    "SCORED": {"CERTIFIED", "REMEDIATING", "HOLD", "REJECT"},
    "CERTIFIED": {"PREPARE_PR", "HOLD"},
}

HEX_LEN = 64


class LedgerIntegrityError(RuntimeError):
    pass


class TaskStateError(RuntimeError):
    pass


class PolicyError(RuntimeError):
    pass


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _valid_ref(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and ("://" in text or text.startswith(("urn:", "sha256:")))


def _valid_hex(value: str) -> bool:
    if len(value) != HEX_LEN:
        return False
    try:
        int(value, 16)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class LedgerRecord:
    sequence: int
    event_type: str
    task_id: str
    occurred_at: int
    payload: Mapping[str, object]
    previous_digest: str
    digest: str


class PersistentRunLedger:
    """Append-only JSONL ledger with a keyed hash chain.

    P1 persists orchestration evidence locally. The caller supplies the ledger
    integrity key; no Production key is embedded in source.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        integrity_key: bytes,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(integrity_key, (bytes, bytearray)) or len(integrity_key) < 16:
            raise ValueError("LEDGER_KEY_TOO_SHORT")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = bytes(integrity_key)
        self._now_fn = now_fn
        if not self.path.exists():
            self.path.touch()
        self.verify()

    def _digest(self, body: Mapping[str, object]) -> str:
        return hmac.new(
            self._key,
            _canonical(body).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def records(self) -> Tuple[LedgerRecord, ...]:
        records: List[LedgerRecord] = []
        previous = "0" * HEX_LEN
        expected_sequence = 1
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise LedgerIntegrityError("LEDGER_READ_FAILED") from exc

        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise LedgerIntegrityError(f"EMPTY_LEDGER_LINE:{line_number}")
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerIntegrityError(f"MALFORMED_LEDGER_JSON:{line_number}") from exc
            required = {
                "sequence",
                "event_type",
                "task_id",
                "occurred_at",
                "payload",
                "previous_digest",
                "digest",
            }
            if set(raw) != required:
                raise LedgerIntegrityError(f"LEDGER_SCHEMA_MISMATCH:{line_number}")
            if raw["sequence"] != expected_sequence:
                raise LedgerIntegrityError(f"LEDGER_SEQUENCE_MISMATCH:{line_number}")
            if raw["previous_digest"] != previous:
                raise LedgerIntegrityError(f"LEDGER_CHAIN_MISMATCH:{line_number}")
            if not isinstance(raw["payload"], dict):
                raise LedgerIntegrityError(f"LEDGER_PAYLOAD_INVALID:{line_number}")
            body = {
                "sequence": raw["sequence"],
                "event_type": raw["event_type"],
                "task_id": raw["task_id"],
                "occurred_at": raw["occurred_at"],
                "payload": raw["payload"],
                "previous_digest": raw["previous_digest"],
            }
            expected_digest = self._digest(body)
            if not _valid_hex(str(raw["digest"])) or not hmac.compare_digest(
                str(raw["digest"]), expected_digest
            ):
                raise LedgerIntegrityError(f"LEDGER_DIGEST_MISMATCH:{line_number}")
            record = LedgerRecord(digest=str(raw["digest"]), **body)
            records.append(record)
            previous = record.digest
            expected_sequence += 1
        return tuple(records)

    def verify(self) -> bool:
        self.records()
        return True

    def append(
        self,
        event_type: str,
        *,
        task_id: str,
        payload: Mapping[str, object],
        occurred_at: Optional[int] = None,
    ) -> LedgerRecord:
        existing = self.records()
        previous = existing[-1].digest if existing else ("0" * HEX_LEN)
        sequence = len(existing) + 1
        body = {
            "sequence": sequence,
            "event_type": str(event_type),
            "task_id": str(task_id),
            "occurred_at": int(self._now_fn()) if occurred_at is None else int(occurred_at),
            "payload": dict(payload),
            "previous_digest": previous,
        }
        digest = self._digest(body)
        raw = dict(body)
        raw["digest"] = digest
        encoded = _canonical(raw) + "\n"
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise LedgerIntegrityError("LEDGER_APPEND_FAILED") from exc
        return LedgerRecord(digest=digest, **body)

    def find_external_event(self, external_event_id: str) -> Optional[LedgerRecord]:
        for record in self.records():
            if record.event_type not in {"EVENT_ACCEPTED", "EVENT_REJECTED"}:
                continue
            if record.payload.get("external_event_id") == external_event_id:
                return record
        return None


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    state: str
    objective: str
    target: str
    risk: str
    reversible: bool
    production: bool
    builder_id: str
    validator_id: str
    certifier_id: str
    max_remediation_attempts: int
    attempts: int
    source_event_id: str
    reason: str


class TaskBoard:
    def __init__(self, ledger: PersistentRunLedger) -> None:
        self.ledger = ledger
        self.rebuild()

    def rebuild(self) -> Dict[str, TaskSnapshot]:
        tasks: Dict[str, TaskSnapshot] = {}
        for record in self.ledger.records():
            if record.event_type == "TASK_CREATED":
                if record.task_id in tasks:
                    raise LedgerIntegrityError("DUPLICATE_TASK_CREATED")
                p = record.payload
                required = {
                    "objective",
                    "target",
                    "risk",
                    "reversible",
                    "production",
                    "builder_id",
                    "validator_id",
                    "certifier_id",
                    "max_remediation_attempts",
                    "source_event_id",
                }
                if set(p) != required:
                    raise LedgerIntegrityError("TASK_CREATED_SCHEMA_MISMATCH")
                tasks[record.task_id] = TaskSnapshot(
                    task_id=record.task_id,
                    state="QUEUED",
                    objective=str(p["objective"]),
                    target=str(p["target"]),
                    risk=str(p["risk"]),
                    reversible=bool(p["reversible"]),
                    production=bool(p["production"]),
                    builder_id=str(p["builder_id"]),
                    validator_id=str(p["validator_id"]),
                    certifier_id=str(p["certifier_id"]),
                    max_remediation_attempts=int(p["max_remediation_attempts"]),
                    attempts=0,
                    source_event_id=str(p["source_event_id"]),
                    reason="CREATED",
                )
            elif record.event_type == "TASK_STATE":
                task = tasks.get(record.task_id)
                if task is None:
                    raise LedgerIntegrityError("STATE_FOR_UNKNOWN_TASK")
                new_state = str(record.payload.get("state") or "")
                reason = str(record.payload.get("reason") or "")
                if new_state not in BOARD_TRANSITIONS.get(task.state, set()):
                    raise LedgerIntegrityError("ILLEGAL_PERSISTED_TASK_TRANSITION")
                tasks[record.task_id] = TaskSnapshot(
                    **{**task.__dict__, "state": new_state, "reason": reason}
                )
            elif record.event_type == "ATTEMPT_STARTED":
                task = tasks.get(record.task_id)
                if task is None:
                    raise LedgerIntegrityError("ATTEMPT_FOR_UNKNOWN_TASK")
                attempt = record.payload.get("attempt")
                if not isinstance(attempt, int) or attempt != task.attempts + 1:
                    raise LedgerIntegrityError("ATTEMPT_SEQUENCE_INVALID")
                tasks[record.task_id] = TaskSnapshot(
                    **{**task.__dict__, "attempts": attempt}
                )
        self._tasks = tasks
        return dict(tasks)

    def get(self, task_id: str) -> TaskSnapshot:
        self.rebuild()
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return self._tasks[task_id]

    def all(self) -> Tuple[TaskSnapshot, ...]:
        self.rebuild()
        return tuple(self._tasks[key] for key in sorted(self._tasks))

    def create(
        self,
        *,
        task_id: str,
        objective: str,
        target: str,
        risk: str,
        reversible: bool,
        production: bool,
        builder_id: str,
        validator_id: str,
        certifier_id: str,
        max_remediation_attempts: int,
        source_event_id: str,
    ) -> TaskSnapshot:
        self.rebuild()
        if task_id in self._tasks:
            raise TaskStateError("TASK_ALREADY_EXISTS")
        if max_remediation_attempts < 0:
            raise PolicyError("INVALID_REMEDIATION_BUDGET")
        payload = {
            "objective": objective,
            "target": target,
            "risk": risk,
            "reversible": reversible,
            "production": production,
            "builder_id": builder_id,
            "validator_id": validator_id,
            "certifier_id": certifier_id,
            "max_remediation_attempts": max_remediation_attempts,
            "source_event_id": source_event_id,
        }
        self.ledger.append("TASK_CREATED", task_id=task_id, payload=payload)
        return self.get(task_id)

    def transition(self, task_id: str, new_state: str, reason: str) -> TaskSnapshot:
        task = self.get(task_id)
        if task.state in TERMINAL_STATES:
            raise TaskStateError("TASK_ALREADY_TERMINAL")
        if new_state not in BOARD_TRANSITIONS.get(task.state, set()):
            raise TaskStateError("ILLEGAL_TASK_TRANSITION")
        self.ledger.append(
            "TASK_STATE",
            task_id=task_id,
            payload={"state": new_state, "reason": reason},
        )
        return self.get(task_id)

    def start_attempt(self, task_id: str) -> TaskSnapshot:
        task = self.get(task_id)
        if task.state not in {"ACTIVE", "REMEDIATING"}:
            raise TaskStateError("ATTEMPT_REQUIRES_ACTIVE_OR_REMEDIATING")
        next_attempt = task.attempts + 1
        if next_attempt > task.max_remediation_attempts + 1:
            raise PolicyError("ATTEMPT_BUDGET_EXHAUSTED")
        self.ledger.append(
            "ATTEMPT_STARTED",
            task_id=task_id,
            payload={"attempt": next_attempt},
        )
        return self.get(task_id)


@dataclass(frozen=True)
class ImprovementEvent:
    event_id: str
    event_type: str
    objective: str
    target: str
    risk: str
    reversible: bool
    production: bool
    evidence_ref: str


@dataclass(frozen=True)
class EventDecision:
    disposition: str
    reason: str
    task_id: Optional[str]


class EventRouter:
    def __init__(self, board: TaskBoard) -> None:
        self.board = board

    def ingest(
        self,
        event: ImprovementEvent,
        *,
        builder_id: str,
        validator_id: str,
        certifier_id: str,
        max_remediation_attempts: int = 2,
    ) -> EventDecision:
        if not event.event_id.strip():
            return EventDecision("HOLD", "EVENT_ID_REQUIRED", None)
        prior = self.board.ledger.find_external_event(event.event_id)
        if prior is not None:
            return EventDecision(
                "DUPLICATE",
                str(prior.payload.get("reason") or "EVENT_ALREADY_SEEN"),
                prior.task_id or None,
            )

        task_id = "caie-" + hashlib.sha256(event.event_id.encode("utf-8")).hexdigest()[:16]
        reason: Optional[str] = None
        disposition = "ACCEPT"
        if event.event_type not in EVENT_TYPES:
            disposition, reason = "HOLD", "UNKNOWN_EVENT_TYPE"
        elif not event.objective.strip():
            disposition, reason = "HOLD", "OBJECTIVE_REQUIRED"
        elif not _valid_ref(event.evidence_ref):
            disposition, reason = "HOLD", "EVIDENCE_REFERENCE_REQUIRED"
        elif event.target in HUMAN_ONLY_TARGETS:
            disposition, reason = "ESCALATE", "HUMAN_ONLY_TARGET"
        elif event.target not in ALLOWED_TARGETS:
            disposition, reason = "HOLD", "UNKNOWN_TARGET"
        elif event.production:
            disposition, reason = "ESCALATE", "PRODUCTION_BOUNDARY"
        elif event.risk not in RISK_LEVELS:
            disposition, reason = "HOLD", "UNKNOWN_RISK"
        elif event.risk == "HIGH":
            disposition, reason = "ESCALATE", "HIGH_RISK"
        elif not event.reversible:
            disposition, reason = "HOLD", "REVERSIBILITY_REQUIRED"
        elif not builder_id.strip() or not validator_id.strip() or not certifier_id.strip():
            disposition, reason = "HOLD", "ROLE_IDENTITY_REQUIRED"
        elif len({builder_id, validator_id, certifier_id}) != 3:
            disposition, reason = "HOLD", "SEPARATION_OF_DUTIES_REQUIRED"
        elif max_remediation_attempts < 0:
            disposition, reason = "HOLD", "INVALID_REMEDIATION_BUDGET"

        if disposition != "ACCEPT":
            self.board.ledger.append(
                "EVENT_REJECTED",
                task_id="",
                payload={
                    "external_event_id": event.event_id,
                    "disposition": disposition,
                    "reason": reason,
                },
            )
            return EventDecision(disposition, str(reason), None)

        self.board.ledger.append(
            "EVENT_ACCEPTED",
            task_id=task_id,
            payload={
                "external_event_id": event.event_id,
                "disposition": "ACCEPT",
                "reason": "BOUNDED_NON_PRODUCTION_EVENT",
                "evidence_ref": event.evidence_ref,
            },
        )
        self.board.create(
            task_id=task_id,
            objective=event.objective,
            target=event.target,
            risk=event.risk,
            reversible=event.reversible,
            production=event.production,
            builder_id=builder_id,
            validator_id=validator_id,
            certifier_id=certifier_id,
            max_remediation_attempts=max_remediation_attempts,
            source_event_id=event.event_id,
        )
        return EventDecision("ACCEPT", "TASK_QUEUED", task_id)


@dataclass(frozen=True)
class ScorerSpec:
    name: str
    threshold: float
    weight: float
    hard_gate: bool
    scorer: Callable[[Mapping[str, object]], float]


@dataclass(frozen=True)
class ScoreItem:
    name: str
    score: float
    threshold: float
    weight: float
    hard_gate: bool
    passed: bool


@dataclass(frozen=True)
class ScoreReport:
    passed: bool
    overall: float
    items: Tuple[ScoreItem, ...]
    reason: str


class ScorerRegistry:
    def __init__(self, *, overall_threshold: float = 0.90) -> None:
        if not 0 <= overall_threshold <= 1:
            raise ValueError("INVALID_OVERALL_THRESHOLD")
        self.overall_threshold = overall_threshold
        self._specs: Dict[str, ScorerSpec] = {}

    def register(
        self,
        name: str,
        scorer: Callable[[Mapping[str, object]], float],
        *,
        threshold: float,
        weight: float = 1.0,
        hard_gate: bool = False,
    ) -> None:
        if not name.strip():
            raise ValueError("SCORER_NAME_REQUIRED")
        if name in self._specs:
            raise ValueError("DUPLICATE_SCORER")
        if not 0 <= threshold <= 1:
            raise ValueError("INVALID_SCORER_THRESHOLD")
        if weight <= 0 or not math.isfinite(weight):
            raise ValueError("INVALID_SCORER_WEIGHT")
        self._specs[name] = ScorerSpec(name, threshold, weight, hard_gate, scorer)

    def evaluate(self, context: Mapping[str, object]) -> ScoreReport:
        if not self._specs:
            return ScoreReport(False, 0.0, tuple(), "NO_SCORERS_REGISTERED")
        items: List[ScoreItem] = []
        weighted_total = 0.0
        weight_total = 0.0
        for name in sorted(self._specs):
            spec = self._specs[name]
            try:
                value = float(spec.scorer(context))
            except Exception:
                return ScoreReport(False, 0.0, tuple(items), f"SCORER_ERROR:{name}")
            if not math.isfinite(value) or value < 0 or value > 1:
                return ScoreReport(False, 0.0, tuple(items), f"SCORER_INVALID:{name}")
            passed = value >= spec.threshold
            item = ScoreItem(
                name=name,
                score=value,
                threshold=spec.threshold,
                weight=spec.weight,
                hard_gate=spec.hard_gate,
                passed=passed,
            )
            items.append(item)
            weighted_total += value * spec.weight
            weight_total += spec.weight
        overall = round(weighted_total / weight_total, 4)
        failed_hard = [item.name for item in items if item.hard_gate and not item.passed]
        if failed_hard:
            return ScoreReport(False, overall, tuple(items), "HARD_GATE_FAILED:" + ",".join(failed_hard))
        if overall < self.overall_threshold:
            return ScoreReport(False, overall, tuple(items), "OVERALL_SCORE_BELOW_THRESHOLD")
        return ScoreReport(True, overall, tuple(items), "SCORING_PASSED")


@dataclass(frozen=True)
class AttemptResult:
    tests_passed: bool
    evidence_ref: str
    context: Mapping[str, object]
    reversible: bool = True
    production: bool = False
    authority_scope: str = "NON_PROD_BRANCH"


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    validator_id: str
    evidence_ref: str


@dataclass(frozen=True)
class CertificationResult:
    passed: bool
    certifier_id: str
    evidence_ref: str
    authority_ceiling: str = AUTONOMOUS_CEILING


class AutonomousRemediationRuntime:
    def __init__(self, board: TaskBoard, scorers: ScorerRegistry) -> None:
        self.board = board
        self.scorers = scorers

    def _record_score(self, task_id: str, report: ScoreReport) -> None:
        self.board.ledger.append(
            "SCORE_RECORDED",
            task_id=task_id,
            payload={
                "passed": report.passed,
                "overall": report.overall,
                "reason": report.reason,
                "items": [
                    {
                        "name": item.name,
                        "score": item.score,
                        "threshold": item.threshold,
                        "weight": item.weight,
                        "hard_gate": item.hard_gate,
                        "passed": item.passed,
                    }
                    for item in report.items
                ],
            },
        )

    def run(
        self,
        task_id: str,
        *,
        executor: Callable[[TaskSnapshot, int], AttemptResult],
        validator: Callable[[TaskSnapshot, AttemptResult], ValidationResult],
        certifier: Callable[[TaskSnapshot, ScoreReport], CertificationResult],
    ) -> TaskSnapshot:
        task = self.board.get(task_id)
        if task.state != "QUEUED":
            raise TaskStateError("RUN_REQUIRES_QUEUED_TASK")
        if task.production:
            return self.board.transition(task_id, "ESCALATE", "PRODUCTION_BOUNDARY")
        if task.target in HUMAN_ONLY_TARGETS:
            return self.board.transition(task_id, "ESCALATE", "HUMAN_ONLY_TARGET")
        if task.target not in ALLOWED_TARGETS:
            return self.board.transition(task_id, "HOLD", "UNKNOWN_TARGET")
        if not task.reversible:
            return self.board.transition(task_id, "HOLD", "REVERSIBILITY_REQUIRED")
        if task.risk not in {"LOW", "MEDIUM"}:
            return self.board.transition(task_id, "ESCALATE", "RISK_THRESHOLD_EXCEEDED")
        if len({task.builder_id, task.validator_id, task.certifier_id}) != 3:
            return self.board.transition(task_id, "HOLD", "SEPARATION_OF_DUTIES_REQUIRED")

        self.board.transition(task_id, "ACTIVE", "AUTONOMOUS_NON_PRODUCTION_RUN_STARTED")

        while True:
            task = self.board.start_attempt(task_id)
            attempt_number = task.attempts
            try:
                attempt = executor(task, attempt_number)
            except Exception as exc:
                self.board.ledger.append(
                    "ATTEMPT_EXCEPTION",
                    task_id=task_id,
                    payload={"attempt": attempt_number, "exception_type": type(exc).__name__},
                )
                if attempt_number <= task.max_remediation_attempts:
                    current = self.board.get(task_id)
                    if current.state == "ACTIVE":
                        self.board.transition(task_id, "VERIFYING", "EXECUTOR_EXCEPTION_REVIEW")
                        self.board.transition(task_id, "REMEDIATING", "EXECUTOR_EXCEPTION_REMEDIATE")
                    elif current.state != "REMEDIATING":
                        return self.board.transition(task_id, "HOLD", "EXECUTOR_EXCEPTION_STATE_INVALID")
                    continue
                current = self.board.get(task_id)
                if current.state == "ACTIVE":
                    return self.board.transition(task_id, "REJECT", "EXECUTOR_EXCEPTION_EXHAUSTED")
                return self.board.transition(task_id, "REJECT", "REMEDIATION_EXHAUSTED")

            if attempt.production:
                return self.board.transition(task_id, "ESCALATE", "ATTEMPT_CROSSED_PRODUCTION_BOUNDARY")
            if not attempt.reversible:
                return self.board.transition(task_id, "HOLD", "ATTEMPT_NOT_REVERSIBLE")
            if attempt.authority_scope != "NON_PROD_BRANCH":
                return self.board.transition(task_id, "HOLD", "ATTEMPT_AUTHORITY_SCOPE_INVALID")
            if not _valid_ref(attempt.evidence_ref):
                return self.board.transition(task_id, "HOLD", "ATTEMPT_EVIDENCE_REQUIRED")

            current = self.board.get(task_id)
            if current.state in {"ACTIVE", "REMEDIATING"}:
                self.board.transition(task_id, "VERIFYING", "ATTEMPT_READY_FOR_INDEPENDENT_VALIDATION")

            task = self.board.get(task_id)
            try:
                validation = validator(task, attempt)
            except Exception as exc:
                self.board.ledger.append(
                    "VALIDATION_EXCEPTION",
                    task_id=task_id,
                    payload={"attempt": attempt_number, "exception_type": type(exc).__name__},
                )
                validation = ValidationResult(False, task.validator_id, "urn:lom:validation:exception")

            if validation.validator_id != task.validator_id or validation.validator_id == task.builder_id:
                return self.board.transition(task_id, "HOLD", "VALIDATOR_IDENTITY_INVALID")
            if not _valid_ref(validation.evidence_ref):
                return self.board.transition(task_id, "HOLD", "VALIDATION_EVIDENCE_REQUIRED")

            if not attempt.tests_passed or not validation.passed:
                if attempt_number <= task.max_remediation_attempts:
                    self.board.transition(task_id, "REMEDIATING", "VALIDATION_FAILED_REMEDIATE")
                    continue
                return self.board.transition(task_id, "REJECT", "REMEDIATION_BUDGET_EXHAUSTED")

            report = self.scorers.evaluate(attempt.context)
            self._record_score(task_id, report)
            if not report.passed:
                if attempt_number <= task.max_remediation_attempts:
                    self.board.transition(task_id, "REMEDIATING", "SCORING_FAILED_REMEDIATE")
                    continue
                return self.board.transition(task_id, "REJECT", report.reason)

            self.board.transition(task_id, "SCORED", "SCORING_AND_VALIDATION_PASSED")
            task = self.board.get(task_id)
            try:
                certification = certifier(task, report)
            except Exception as exc:
                self.board.ledger.append(
                    "CERTIFICATION_EXCEPTION",
                    task_id=task_id,
                    payload={"exception_type": type(exc).__name__},
                )
                return self.board.transition(task_id, "HOLD", "CERTIFICATION_EXCEPTION")
            if certification.certifier_id != task.certifier_id:
                return self.board.transition(task_id, "HOLD", "CERTIFIER_IDENTITY_INVALID")
            if certification.certifier_id in {task.builder_id, task.validator_id}:
                return self.board.transition(task_id, "HOLD", "CERTIFIER_NOT_INDEPENDENT")
            if not certification.passed:
                return self.board.transition(task_id, "HOLD", "CERTIFICATION_FAILED")
            if not _valid_ref(certification.evidence_ref):
                return self.board.transition(task_id, "HOLD", "CERTIFICATION_EVIDENCE_REQUIRED")
            if certification.authority_ceiling != AUTONOMOUS_CEILING:
                return self.board.transition(task_id, "HOLD", "AUTHORITY_CEILING_INVALID")

            self.board.transition(task_id, "CERTIFIED", "INDEPENDENT_CERTIFICATION_PASSED")
            self.board.ledger.append(
                "RELEASE_CANDIDATE",
                task_id=task_id,
                payload={
                    "authority_ceiling": AUTONOMOUS_CEILING,
                    "merge_executed": False,
                    "production_deployed": False,
                    "production_locked": True,
                },
            )
            return self.board.transition(task_id, "PREPARE_PR", "AUTONOMOUS_CEILING_REACHED")

    def merge_protected_main(self) -> None:
        raise PermissionError("HUMAN_APPROVAL_REQUIRED")

    def deploy_production(self) -> None:
        raise PermissionError("HUMAN_APPROVAL_REQUIRED")
