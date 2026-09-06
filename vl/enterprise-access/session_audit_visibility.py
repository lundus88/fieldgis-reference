from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional

ALLOWED_OUTCOMES = {"ALLOW", "DENY", "HOLD", "ERROR"}
SENSITIVE_KEYS = {
    "secret", "token", "password", "authorization", "cookie", "api_key", "apikey",
    "access_token", "refresh_token", "private_key", "credential", "credentials"
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def _redact_mapping(value: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, item in value.items():
        normalized = key.lower()
        if normalized in SENSITIVE_KEYS or any(part in normalized for part in ("secret", "token", "password", "credential")):
            result[key] = "[REDACTED]"
        elif isinstance(item, Mapping):
            result[key] = _redact_mapping(item)
        elif isinstance(item, list):
            result[key] = [
                _redact_mapping(x) if isinstance(x, Mapping) else x
                for x in item
            ]
        else:
            result[key] = item
    return result


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    actor_id: str
    workspace_id: str
    project_id: Optional[str]
    device_id: str
    device_trust: str
    auth_method: str
    issued_at: str
    expires_at: str

    def public_view(self) -> Dict[str, Any]:
        data = asdict(self)
        data["session_fingerprint"] = _digest({
            "session_id": self.session_id,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "device_id": self.device_id,
            "issued_at": self.issued_at,
        })
        del data["session_id"]
        return data


@dataclass(frozen=True)
class AuditEvent:
    actor_id: str
    workspace_id: str
    project_id: Optional[str]
    action: str
    policy_id: str
    policy_version: str
    outcome: str
    reason: str
    session_fingerprint: str
    device_id: str
    device_trust: str
    auth_method: str
    resource_scope: str
    occurred_at: str
    metadata: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        if self.outcome not in ALLOWED_OUTCOMES:
            raise ValueError("INVALID_AUDIT_OUTCOME")
        event = asdict(self)
        event["metadata"] = _redact_mapping(dict(self.metadata))
        event["schema"] = "vl.enterprise-audit-event/1"
        event["event_sha256"] = _digest(event)
        return event


def build_audit_event(
    *,
    session: SessionContext,
    action: str,
    policy_id: str,
    policy_version: str,
    outcome: str,
    reason: str,
    resource_scope: str,
    occurred_at: str,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    public_session = session.public_view()
    return AuditEvent(
        actor_id=session.actor_id,
        workspace_id=session.workspace_id,
        project_id=session.project_id,
        action=action,
        policy_id=policy_id,
        policy_version=policy_version,
        outcome=outcome,
        reason=reason,
        session_fingerprint=public_session["session_fingerprint"],
        device_id=session.device_id,
        device_trust=session.device_trust,
        auth_method=session.auth_method,
        resource_scope=resource_scope,
        occurred_at=occurred_at,
        metadata=metadata or {},
    ).to_dict()


def list_visible_sessions(
    sessions: Iterable[SessionContext],
    *,
    viewer_actor_id: str,
    viewer_workspace_ids: Iterable[str],
    can_audit_workspace: bool,
) -> List[Dict[str, Any]]:
    allowed_workspaces = set(viewer_workspace_ids)
    visible: List[Dict[str, Any]] = []
    for session in sessions:
        same_actor = session.actor_id == viewer_actor_id
        workspace_auditable = can_audit_workspace and session.workspace_id in allowed_workspaces
        if same_actor or workspace_auditable:
            visible.append(session.public_view())
    return visible
