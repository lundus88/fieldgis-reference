from __future__ import annotations

from datetime import datetime, timezone

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

AUTONOMOUSLY_FORBIDDEN = {"production.approve", "production.promote"}


def _deny(action_id: str, reason: str, effective: set[str] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "action_id": action_id,
        "decision": "deny",
        "reason_code": reason,
        "policy_version": "reference-v1",
        "effective_capabilities": sorted(effective or set()),
    }


def evaluate(action: dict, grant: dict, *, seen_action_ids: set[str] | None = None, now: datetime | None = None) -> dict:
    """Reference fail-closed evaluator for contract/adversarial CI tests only.

    This is not yet the production runtime policy engine.
    """
    seen_action_ids = seen_action_ids or set()
    now = now or datetime.now(timezone.utc)
    action_id = str(action.get("action_id") or "")
    capability = str(action.get("capability") or "")
    effective = set(grant.get("capabilities") or [])

    if not action.get("provenance") or not action["provenance"].get("source_id"):
        return _deny(action_id, "DENY_MISSING_PROVENANCE", effective)
    if action_id in seen_action_ids:
        return _deny(action_id, "DENY_REPLAY", effective)

    try:
        expires = datetime.fromisoformat(str(action["expires_at"]).replace("Z", "+00:00"))
    except Exception:
        return _deny(action_id, "DENY_EXPIRED_ACTION", effective)
    if expires <= now:
        return _deny(action_id, "DENY_EXPIRED_ACTION", effective)

    if capability in AUTONOMOUSLY_FORBIDDEN:
        return {
            "schema_version": "1.0",
            "action_id": action_id,
            "decision": "require_human_approval",
            "reason_code": "REQUIRE_HUMAN_PRODUCTION_APPROVAL",
            "policy_version": "reference-v1",
            "effective_capabilities": sorted(effective),
            "human_approval_required": True,
        }

    if capability.startswith("connector.invoke:"):
        known = True
    else:
        known = capability in KNOWN_CAPABILITIES
    if not known:
        return _deny(action_id, "DENY_UNKNOWN_CAPABILITY", effective)
    if capability not in effective:
        return _deny(action_id, "DENY_CAPABILITY_NOT_GRANTED", effective)

    requested_scope = action.get("scope") or {}
    allowed_scope = grant.get("scope") or {}
    for key, value in requested_scope.items():
        if key not in allowed_scope or allowed_scope[key] != value:
            return _deny(action_id, "DENY_SCOPE_MISMATCH", effective)

    delegated = set(grant.get("delegated_capabilities") or effective)
    if not delegated.issubset(effective):
        return _deny(action_id, "DENY_DELEGATION_ESCALATION", effective)

    return {
        "schema_version": "1.0",
        "action_id": action_id,
        "decision": "allow",
        "reason_code": "ALLOW_POLICY_MATCH",
        "policy_version": "reference-v1",
        "effective_capabilities": sorted(effective),
    }
