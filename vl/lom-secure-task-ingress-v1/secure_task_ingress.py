from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re
from typing import Any

SCHEMA = "lom.secure-task-ingress/1"
ALLOWED_ACTIONS = {
    "PREPARE_PREVIEW_REFRESH",
    "PREPARE_EXACT_MAIN_CI_REFRESH",
    "PREPARE_CI_REMEDIATION_PR",
    "PREPARE_RUNTIME_DIAGNOSTIC_PR",
    "PREPARE_REGRESSION_EVIDENCE_REFRESH",
    "PREPARE_JOURNEY_BINDING_PR",
    "PREPARE_NONCRITICAL_REMEDIATION_PR",
    "NON_PROD_CODE",
}
FORBIDDEN_CAPABILITY_PREFIXES = ("production.", "connector.invoke:")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{16,200}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + sha256(canonical_bytes(value)).hexdigest()


def sign_task(task: dict[str, Any], secret: bytes) -> str:
    if not secret:
        raise ValueError("SIGNING_SECRET_REQUIRED")
    return "hmac-sha256:" + hmac.new(secret, canonical_bytes(task), sha256).hexdigest()


def verify_signature(task: dict[str, Any], signature: str, secret: bytes) -> bool:
    if not secret or not isinstance(signature, str) or not signature.startswith("hmac-sha256:"):
        return False
    expected = sign_task(task, secret)
    return hmac.compare_digest(expected, signature)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class QueueEntry:
    task_id: str
    priority: int
    tenant: str
    accepted_at: str
    envelope_digest: str
    envelope: dict[str, Any]


class SecureTaskIngress:
    """Authenticated, fail-closed ingress buffer for bounded non-Production LOM tasks.

    This component does not grant authority and does not execute tasks. It only
    accepts an already bounded request after signature, freshness, scope and
    replay checks. ACP and the VPS executor remain authoritative downstream.
    """

    def __init__(self, *, secret: bytes, max_queue: int = 64, max_ttl_seconds: int = 900) -> None:
        if not secret:
            raise ValueError("SIGNING_SECRET_REQUIRED")
        if max_queue < 1 or max_queue > 1024:
            raise ValueError("QUEUE_BOUND_INVALID")
        if max_ttl_seconds < 30 or max_ttl_seconds > 3600:
            raise ValueError("TTL_BOUND_INVALID")
        self.secret = secret
        self.max_queue = max_queue
        self.max_ttl_seconds = max_ttl_seconds
        self._queue: list[QueueEntry] = []
        self._seen: dict[str, str] = {}

    def _hold(self, reason: str, **extra: Any) -> dict[str, Any]:
        return {
            "decision": "HOLD",
            "reason": reason,
            "production": False,
            "production_locked": True,
            **extra,
        }

    def submit(
        self,
        envelope: dict[str, Any],
        signature: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if not isinstance(envelope, dict):
            return self._hold("ENVELOPE_OBJECT_REQUIRED")
        if not verify_signature(envelope, signature, self.secret):
            return self._hold("SIGNATURE_INVALID")

        required = {
            "schema", "task_id", "issued_at", "expires_at", "tenant", "priority",
            "idempotency_key", "body_request", "grant", "evidence_refs",
        }
        if set(envelope) != required:
            return self._hold("ENVELOPE_FIELDS_INVALID")
        if envelope.get("schema") != SCHEMA:
            return self._hold("INGRESS_SCHEMA_INVALID")

        task_id = str(envelope.get("task_id") or "")
        if not TASK_ID_RE.fullmatch(task_id):
            return self._hold("TASK_ID_INVALID")

        issued = _parse_time(envelope.get("issued_at"))
        expires = _parse_time(envelope.get("expires_at"))
        if issued is None or expires is None or expires <= issued:
            return self._hold("TASK_TIME_INVALID")
        if issued > now or expires <= now:
            return self._hold("TASK_EXPIRED_OR_FUTURE")
        ttl = int((expires - issued).total_seconds())
        if ttl > self.max_ttl_seconds:
            return self._hold("TASK_TTL_EXCEEDS_BOUND")

        priority = envelope.get("priority")
        if not isinstance(priority, int) or priority < 0 or priority > 100:
            return self._hold("PRIORITY_INVALID")
        tenant = str(envelope.get("tenant") or "")
        if not tenant or len(tenant) > 128:
            return self._hold("TENANT_INVALID")

        idem = str(envelope.get("idempotency_key") or "")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", idem):
            return self._hold("IDEMPOTENCY_KEY_INVALID")

        body = envelope.get("body_request")
        grant = envelope.get("grant")
        evidence_refs = envelope.get("evidence_refs")
        if not isinstance(body, dict) or not isinstance(grant, dict):
            return self._hold("BOUNDED_REQUEST_AND_GRANT_REQUIRED")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            return self._hold("INGRESS_EVIDENCE_REQUIRED")

        if body.get("schema") != "lom.organism-bounded-delegation/1":
            return self._hold("BODY_SCHEMA_INVALID")
        if body.get("production") is not False or body.get("production_locked") is not True:
            return self._hold("PRODUCTION_BOUNDARY_INVALID")
        if body.get("max_authority") != "PREPARE_PR":
            return self._hold("AUTHORITY_CEILING_INVALID")
        if body.get("requested_action") not in ALLOWED_ACTIONS:
            return self._hold("BODY_ACTION_NOT_REGISTERED")
        if body.get("idempotency_key") != idem:
            return self._hold("IDEMPOTENCY_BINDING_MISMATCH")
        if body.get("evidence_refs") != evidence_refs:
            return self._hold("EVIDENCE_BINDING_MISMATCH")

        scope = grant.get("scope") or {}
        capability_set = set(grant.get("capabilities") or [])
        if scope.get("target_environment") not in {"development", "staging"}:
            return self._hold("NON_PRODUCTION_SCOPE_REQUIRED")
        if body.get("project_id") != scope.get("project_id"):
            return self._hold("PROJECT_SCOPE_MISMATCH")
        if "factory.plan" not in capability_set:
            return self._hold("FACTORY_PLAN_GRANT_REQUIRED")
        if any(cap.startswith(FORBIDDEN_CAPABILITY_PREFIXES) for cap in capability_set):
            return self._hold("FORBIDDEN_CAPABILITY_PRESENT")

        envelope_digest = digest(envelope)
        previous = self._seen.get(task_id)
        if previous is not None:
            if previous == envelope_digest:
                return {
                    "decision": "ACCEPTED_IDEMPOTENT",
                    "reason": "IDENTICAL_TASK_ALREADY_ACCEPTED",
                    "task_id": task_id,
                    "production": False,
                    "production_locked": True,
                }
            return self._hold("TASK_ID_REPLAY_MISMATCH")

        if len(self._queue) >= self.max_queue:
            return self._hold("QUEUE_CAPACITY_REACHED")

        entry = QueueEntry(
            task_id=task_id,
            priority=priority,
            tenant=tenant,
            accepted_at=now.isoformat().replace("+00:00", "Z"),
            envelope_digest=envelope_digest,
            envelope=envelope,
        )
        self._queue.append(entry)
        self._seen[task_id] = envelope_digest
        return {
            "decision": "ACCEPTED",
            "reason": "AUTHENTICATED_BOUNDED_TASK_BUFFERED",
            "task_id": task_id,
            "queue_depth": len(self._queue),
            "envelope_digest": envelope_digest,
            "production": False,
            "production_locked": True,
            "execution_performed": False,
        }

    def claim_next(self) -> dict[str, Any]:
        if not self._queue:
            return self._hold("QUEUE_EMPTY")
        # Fairness: first pass chooses highest priority tenant head, then oldest.
        self._queue.sort(key=lambda item: (-item.priority, item.accepted_at, item.tenant, item.task_id))
        entry = self._queue.pop(0)
        return {
            "decision": "CLAIMED",
            "reason": "INGRESS_BUFFER_RELEASED_TO_ACP",
            "task_id": entry.task_id,
            "envelope_digest": entry.envelope_digest,
            "envelope": entry.envelope,
            "queue_depth": len(self._queue),
            "production": False,
            "production_locked": True,
        }

    def status(self) -> dict[str, Any]:
        return {
            "schema": "lom.secure-task-ingress-status/1",
            "queue_depth": len(self._queue),
            "queue_capacity": self.max_queue,
            "production": False,
            "production_locked": True,
            "self_grant": "FORBIDDEN",
            "arbitrary_shell": "FORBIDDEN",
            "connector_execution": "FORBIDDEN",
            "autonomous_ceiling": "PREPARE_PR",
        }
