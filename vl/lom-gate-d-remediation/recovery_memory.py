from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

ALLOWED_OUTCOMES = {"RECOVERED", "FAILED", "FAILED_VALIDATION", "HOLD", "ESCALATE"}
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class FailureSignal:
    failure_id: str
    run_id: str
    project_id: str
    component: str
    failure_class: str
    error_code: str
    environment: str
    risk: str
    reversible: bool
    evidence_refs: tuple[str, ...]
    timestamp_epoch: int

    @property
    def fingerprint(self) -> str:
        return _fingerprint({
            "project_id": self.project_id,
            "component": self.component,
            "failure_class": self.failure_class,
            "error_code": self.error_code,
            "environment": self.environment,
        })


@dataclass(frozen=True)
class RecoveryAttempt:
    attempt_id: str
    run_id: str
    failure_fingerprint: str
    action: str
    outcome: str
    evidence_refs: tuple[str, ...]
    independently_validated: bool
    timestamp_epoch: int


class RecurrentFailureMemory:
    """Cross-run recovery memory.

    Advisory only. This component never executes remediation and never widens
    the Gate D delegation/authority envelope.
    """

    def __init__(self):
        self._failures: dict[str, FailureSignal] = {}
        self._attempts: dict[str, RecoveryAttempt] = {}

    def observe(self, signal: FailureSignal) -> dict:
        if not signal.failure_id or not signal.run_id or not signal.project_id:
            raise ValueError("FAILURE_ID_RUN_ID_PROJECT_ID_REQUIRED")
        if not signal.component or not signal.failure_class or not signal.error_code:
            raise ValueError("FAILURE_SIGNATURE_INCOMPLETE")
        if signal.environment not in {"NON_PRODUCTION", "PRODUCTION"}:
            raise ValueError("UNKNOWN_ENVIRONMENT")
        if signal.risk not in RISK_ORDER:
            raise ValueError("UNKNOWN_RISK")
        if not signal.evidence_refs:
            raise ValueError("EVIDENCE_REQUIRED")
        if not isinstance(signal.timestamp_epoch, int) or isinstance(signal.timestamp_epoch, bool):
            raise ValueError("INVALID_TIMESTAMP")

        existing = self._failures.get(signal.failure_id)
        if existing:
            if existing != signal:
                raise ValueError("FAILURE_ID_COLLISION")
            return self.describe(signal.fingerprint)

        self._failures[signal.failure_id] = signal
        return self.describe(signal.fingerprint)

    def record_attempt(self, attempt: RecoveryAttempt) -> dict:
        if not attempt.attempt_id or not attempt.run_id or not attempt.action:
            raise ValueError("ATTEMPT_ID_RUN_ID_ACTION_REQUIRED")
        if attempt.outcome not in ALLOWED_OUTCOMES:
            raise ValueError("UNKNOWN_OUTCOME")
        if not attempt.evidence_refs:
            raise ValueError("EVIDENCE_REQUIRED")
        if not isinstance(attempt.timestamp_epoch, int) or isinstance(attempt.timestamp_epoch, bool):
            raise ValueError("INVALID_TIMESTAMP")
        if attempt.failure_fingerprint not in {item.fingerprint for item in self._failures.values()}:
            raise ValueError("UNKNOWN_FAILURE_FINGERPRINT")
        if attempt.outcome == "RECOVERED" and not attempt.independently_validated:
            raise ValueError("RECOVERY_REQUIRES_INDEPENDENT_VALIDATION")

        existing = self._attempts.get(attempt.attempt_id)
        if existing:
            if existing != attempt:
                raise ValueError("ATTEMPT_ID_COLLISION")
            return self.describe(attempt.failure_fingerprint)

        self._attempts[attempt.attempt_id] = attempt
        return self.describe(attempt.failure_fingerprint)

    def describe(self, failure_fingerprint: str) -> dict:
        failures = [item for item in self._failures.values() if item.fingerprint == failure_fingerprint]
        attempts = [item for item in self._attempts.values() if item.failure_fingerprint == failure_fingerprint]
        failed_actions = sorted({
            item.action for item in attempts
            if item.outcome in {"FAILED", "FAILED_VALIDATION", "HOLD", "ESCALATE"}
        })
        known_good_actions = sorted({
            item.action for item in attempts
            if item.outcome == "RECOVERED" and item.independently_validated
        })
        return {
            "failure_fingerprint": failure_fingerprint,
            "recurrence_count": len(failures),
            "distinct_run_count": len({item.run_id for item in failures}),
            "attempt_count": len(attempts),
            "failed_actions": failed_actions,
            "known_good_actions": known_good_actions,
        }

    def recommend(
        self,
        signal: FailureSignal,
        *,
        delegated_actions: Iterable[str],
        candidate_actions: Iterable[str],
    ) -> dict:
        """Return a bounded recovery route without executing anything."""
        base = {
            "failure_fingerprint": signal.fingerprint,
            "execution_authority": "NONE",
            "execution_performed": False,
            "production_authority": "HUMAN_ONLY",
            "autonomous_ceiling": "PREPARE_PR",
        }

        if not signal.evidence_refs:
            return {**base, "decision": "HOLD", "reason": "EVIDENCE_REQUIRED", "action": None}
        if signal.environment == "PRODUCTION":
            return {**base, "decision": "ESCALATE", "reason": "PRODUCTION_BOUNDARY", "action": None}
        if signal.environment != "NON_PRODUCTION":
            return {**base, "decision": "HOLD", "reason": "UNKNOWN_ENVIRONMENT", "action": None}
        if signal.risk not in RISK_ORDER:
            return {**base, "decision": "HOLD", "reason": "UNKNOWN_RISK", "action": None}
        if signal.risk != "LOW":
            return {**base, "decision": "ESCALATE", "reason": "RISK_THRESHOLD_EXCEEDED", "action": None}
        if not signal.reversible:
            return {**base, "decision": "HOLD", "reason": "NOT_REVERSIBLE", "action": None}

        delegated = tuple(dict.fromkeys(delegated_actions))
        candidates = tuple(dict.fromkeys(candidate_actions))
        allowed = [action for action in candidates if action in delegated]
        if not allowed:
            return {**base, "decision": "HOLD", "reason": "NO_DELEGATED_RECOVERY_ROUTE", "action": None}

        history = self.describe(signal.fingerprint)
        known_good = [action for action in allowed if action in history["known_good_actions"]]
        if known_good:
            return {
                **base,
                "decision": "PREPARE_REMEDIATION",
                "reason": "KNOWN_GOOD_RECOVERY_ROUTE",
                "action": known_good[0],
                "recurrence_count": history["recurrence_count"],
            }

        untried = [action for action in allowed if action not in history["failed_actions"]]
        if untried:
            reason = "SAFE_FALLBACK_ROUTE" if history["attempt_count"] else "BOUNDED_RECOVERY_ROUTE"
            return {
                **base,
                "decision": "PREPARE_REMEDIATION",
                "reason": reason,
                "action": untried[0],
                "recurrence_count": history["recurrence_count"],
            }

        if history["recurrence_count"] >= 2:
            return {
                **base,
                "decision": "ESCALATE",
                "reason": "RECURRENT_FAILURE_REQUIRES_HUMAN",
                "action": None,
                "recurrence_count": history["recurrence_count"],
            }

        return {
            **base,
            "decision": "HOLD",
            "reason": "RECOVERY_LOOP_PREVENTED",
            "action": None,
            "recurrence_count": history["recurrence_count"],
        }
