from dataclasses import dataclass, field
from typing import Any, Dict, List

HOLD = "HOLD"
READY = "READY"
RUNNING = "RUNNING"
VALIDATING = "VALIDATING"
COMPLETED = "COMPLETED"
ESCALATED = "ESCALATED"
FAILED = "FAILED"

@dataclass
class Task:
    task_id: str
    action: str
    evidence: List[str] = field(default_factory=list)
    risk_class: str = "LOW"
    actor: str = "EXECUTOR"
    attempts: int = 0
    status: str = HOLD
    output: Any = None
    error_class: str | None = None

class Runtime:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self.ledger: List[Dict[str, Any]] = []

    def _record(self, task: Task, event: str, reason: str = "") -> None:
        self.ledger.append({
            "task_id": task.task_id,
            "event": event,
            "status": task.status,
            "actor": task.actor,
            "attempts": task.attempts,
            "reason": reason,
            "evidence": list(task.evidence),
        })

    def classify(self, task: Task) -> str:
        if task.action in self.policy["human_only_actions"]:
            task.status = ESCALATED
            task.error_class = "HUMAN_ONLY_ACTION"
            self._record(task, "ESCALATE", task.error_class)
            return task.status
        if task.action not in self.policy["allowed_autonomous_actions"]:
            task.status = ESCALATED
            task.error_class = "UNKNOWN_AUTHORITY"
            self._record(task, "ESCALATE", task.error_class)
            return task.status
        if not task.evidence:
            task.status = ESCALATED
            task.error_class = "MISSING_REQUIRED_EVIDENCE"
            self._record(task, "ESCALATE", task.error_class)
            return task.status
        if task.risk_class not in {"LOW", "MEDIUM"}:
            task.status = ESCALATED
            task.error_class = "RISK_THRESHOLD_EXCEEDED"
            self._record(task, "ESCALATE", task.error_class)
            return task.status
        task.status = READY
        self._record(task, "CLASSIFIED")
        return task.status

    def execute(self, task: Task, executor) -> str:
        if self.classify(task) != READY:
            return task.status
        max_attempts = 1 + int(self.policy["max_retry_attempts"])
        while task.attempts < max_attempts:
            task.attempts += 1
            task.status = RUNNING
            self._record(task, "EXECUTE")
            try:
                task.output = executor(task)
                task.status = VALIDATING
                self._record(task, "EXECUTION_COMPLETE")
                return task.status
            except Exception as exc:
                task.error_class = getattr(exc, "error_class", "UNCLASSIFIED_ERROR")
                retryable = task.error_class in self.policy["retryable_failure_classes"]
                if retryable and task.attempts < max_attempts:
                    self._record(task, "RETRY", task.error_class)
                    continue
                task.status = ESCALATED if task.error_class in self.policy["non_retryable_failure_classes"] else FAILED
                self._record(task, "EXECUTION_STOP", task.error_class)
                return task.status
        task.status = FAILED
        self._record(task, "EXECUTION_STOP", "RETRY_EXHAUSTED")
        return task.status

    def validate(self, task: Task, validator) -> str:
        if task.status != VALIDATING:
            return task.status
        if task.actor == "VALIDATOR":
            task.status = ESCALATED
            task.error_class = "SELF_CERTIFICATION_FORBIDDEN"
            self._record(task, "ESCALATE", task.error_class)
            return task.status
        verdict = validator(task)
        if verdict is True:
            task.status = COMPLETED
            self._record(task, "VALIDATED")
        else:
            task.status = ESCALATED
            task.error_class = "VALIDATION_FAILED"
            self._record(task, "ESCALATE", task.error_class)
        return task.status
