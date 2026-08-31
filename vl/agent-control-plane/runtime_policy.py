from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterable

KNOWN_CAPABILITIES = {
    "spec.read",
    "spec.propose",
    "factory.plan",
    "factory.enqueue",
    "artifact.read",
    "qa.execute",
    "certification.propose",
    "release.request_approval",
}
HUMAN_ONLY_CAPABILITIES = {"production.approve"}
GATED_PRODUCTION_CAPABILITIES = {"production.promote"}
POLICY_VERSION = "acp-runtime-v1"


@dataclass(frozen=True)
class PolicyError(Exception):
    reason_code: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _decision(action_id: str, decision: str, reason: str, effective: Iterable[str] = (), **extra: Any) -> dict[str, Any]:
    out = {
        "schema_version": "1.0",
        "action_id": action_id,
        "decision": decision,
        "reason_code": reason,
        "decided_at": utcnow().isoformat().replace("+00:00", "Z"),
        "policy_version": POLICY_VERSION,
        "effective_capabilities": sorted(set(effective)),
    }
    out.update(extra)
    return out


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise PolicyError("DENY_EXPIRED_ACTION")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PolicyError("DENY_EXPIRED_ACTION") from exc
    if dt.tzinfo is None:
        raise PolicyError("DENY_EXPIRED_ACTION")
    return dt.astimezone(timezone.utc)


def evaluate_runtime(
    action: dict[str, Any],
    grant: dict[str, Any] | None,
    *,
    replay_record: dict[str, str] | None = None,
    now: datetime | None = None,
    policy_available: bool = True,
) -> dict[str, Any]:
    """Pure runtime policy evaluator for ACP V1.

    This function is suitable for wiring into a future enforcement service, but this
    module alone does not alter factory state or invoke connectors. It never reads
    ambient credentials and fails closed when policy evidence is unavailable.
    """
    now = (now or utcnow()).astimezone(timezone.utc)
    action_id = str(action.get("action_id") or "")

    if not policy_available or not isinstance(grant, dict):
        return _decision(action_id, "deny", "DENY_POLICY_UNAVAILABLE")

    effective = set(grant.get("capabilities") or [])
    provenance = action.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("source_type") or not provenance.get("source_id"):
        return _decision(action_id, "deny", "DENY_MISSING_PROVENANCE", effective)

    requested_at = action.get("requested_at")
    expires_at = action.get("expires_at")
    try:
        requested = _parse_time(requested_at)
        expires = _parse_time(expires_at)
    except PolicyError as err:
        return _decision(action_id, "deny", err.reason_code, effective)
    if expires <= now or expires <= requested:
        return _decision(action_id, "deny", "DENY_EXPIRED_ACTION", effective)

    declared_digest = str(action.get("input_digest") or "")
    if not declared_digest.startswith("sha256:") or len(declared_digest) != 71:
        return _decision(action_id, "deny", "DENY_MISSING_PROVENANCE", effective)

    if replay_record is not None and action_id in replay_record:
        if replay_record[action_id] == declared_digest:
            return _decision(action_id, "allow", "ALLOW_POLICY_MATCH", effective, replayed=True)
        return _decision(action_id, "deny", "DENY_REPLAY", effective)

    capability = str(action.get("capability") or "")
    if capability in HUMAN_ONLY_CAPABILITIES:
        return _decision(
            action_id,
            "require_human_approval",
            "REQUIRE_HUMAN_PRODUCTION_APPROVAL",
            effective,
            human_approval_required=True,
        )
    if capability in GATED_PRODUCTION_CAPABILITIES:
        return _decision(
            action_id,
            "require_human_approval",
            "REQUIRE_HUMAN_PRODUCTION_APPROVAL",
            effective,
            human_approval_required=True,
        )

    known = capability in KNOWN_CAPABILITIES or capability.startswith("connector.invoke:")
    if not known:
        return _decision(action_id, "deny", "DENY_UNKNOWN_CAPABILITY", effective)
    if capability not in effective:
        return _decision(action_id, "deny", "DENY_CAPABILITY_NOT_GRANTED", effective)

    requested_scope = action.get("scope")
    allowed_scope = grant.get("scope")
    if not isinstance(requested_scope, dict) or not requested_scope or not isinstance(allowed_scope, dict):
        return _decision(action_id, "deny", "DENY_SCOPE_MISMATCH", effective)
    for key, value in requested_scope.items():
        if key not in allowed_scope or allowed_scope[key] != value:
            return _decision(action_id, "deny", "DENY_SCOPE_MISMATCH", effective)

    delegated = set(grant.get("delegated_capabilities") or effective)
    if not delegated.issubset(effective):
        return _decision(action_id, "deny", "DENY_DELEGATION_ESCALATION", effective)

    parent_scope = grant.get("parent_scope")
    if isinstance(parent_scope, dict):
        for key, value in allowed_scope.items():
            if key in parent_scope and parent_scope[key] != value:
                return _decision(action_id, "deny", "DENY_SCOPE_MISMATCH", effective)

    budget = action.get("budget") or {}
    grant_budget = grant.get("budget") or {}
    for key in ("timeout_seconds", "max_retries", "max_cost_minor"):
        requested_value = budget.get(key)
        limit = grant_budget.get(key)
        if requested_value is not None and limit is not None and requested_value > limit:
            return _decision(action_id, "deny", "DENY_DELEGATION_ESCALATION", effective)

    return _decision(action_id, "allow", "ALLOW_POLICY_MATCH", effective, replayed=False)
