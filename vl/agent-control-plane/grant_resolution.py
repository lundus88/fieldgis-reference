from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


class GrantResolutionError(Exception):
    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class ResolvedGrant:
    grant_id: str
    agent_id: str
    capabilities: frozenset[str]
    scope: Mapping[str, Any]
    budget: Mapping[str, int | None]
    chain: tuple[str, ...]

    def as_runtime_grant(self) -> dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "agent_id": self.agent_id,
            "capabilities": sorted(self.capabilities),
            "delegated_capabilities": sorted(self.capabilities),
            "scope": dict(self.scope),
            "budget": dict(self.budget),
            "delegation_chain": list(self.chain),
        }


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GrantResolutionError("DENY_POLICY_UNAVAILABLE") from exc
    if dt.tzinfo is None:
        raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")
    return dt.astimezone(timezone.utc)


def _scope_subset(child: Mapping[str, Any], parent: Mapping[str, Any]) -> bool:
    if not child:
        return False
    for key, value in child.items():
        if key not in parent or parent[key] != value:
            return False
    return True


def _budget_not_wider(child: Mapping[str, Any], parent: Mapping[str, Any]) -> bool:
    for key in ("timeout_seconds", "max_retries", "max_cost_minor"):
        child_value = child.get(key)
        parent_value = parent.get(key)
        if child_value is None:
            continue
        if parent_value is None:
            # Parent with no ceiling may delegate a bounded child value.
            continue
        if child_value > parent_value:
            return False
    return True


def resolve_grant(
    grant_id: str,
    grants_by_id: Mapping[str, Mapping[str, Any]],
    *,
    expected_agent_id: str | None = None,
    now: datetime | None = None,
    max_depth: int = 16,
) -> ResolvedGrant:
    """Resolve a persisted grant and prove monotonic-restrictive delegation.

    The input is deliberately storage-agnostic: callers must load rows from the
    authoritative private grant store. Missing/invalid policy evidence fails closed.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not grant_id or not isinstance(grants_by_id, Mapping):
        raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")

    chain_rows: list[Mapping[str, Any]] = []
    chain_ids: list[str] = []
    seen: set[str] = set()
    current_id: str | None = grant_id

    while current_id is not None:
        if current_id in seen:
            raise GrantResolutionError("DENY_DELEGATION_ESCALATION")
        if len(chain_rows) >= max_depth:
            raise GrantResolutionError("DENY_DELEGATION_ESCALATION")
        seen.add(current_id)

        row = grants_by_id.get(current_id)
        if not isinstance(row, Mapping):
            raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")
        if str(row.get("grant_id") or current_id) != current_id:
            raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")
        if row.get("revoked_at") is not None:
            raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")
        valid_until = row.get("valid_until")
        if valid_until is not None and _utc(valid_until) <= now:
            raise GrantResolutionError("DENY_EXPIRED_ACTION")

        chain_rows.append(row)
        chain_ids.append(current_id)
        parent = row.get("delegated_from_grant_id")
        current_id = str(parent) if parent else None

    leaf = chain_rows[0]
    leaf_agent = str(leaf.get("agent_id") or "")
    if not leaf_agent:
        raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")
    if expected_agent_id is not None and leaf_agent != expected_agent_id:
        raise GrantResolutionError("DENY_SCOPE_MISMATCH")

    leaf_caps = frozenset(str(v) for v in (leaf.get("capabilities") or []) if str(v))
    leaf_scope = leaf.get("scope") or {}
    leaf_budget = leaf.get("budget") or {}
    if not leaf_caps or not isinstance(leaf_scope, Mapping) or not leaf_scope or not isinstance(leaf_budget, Mapping):
        raise GrantResolutionError("DENY_POLICY_UNAVAILABLE")

    for child, parent in zip(chain_rows, chain_rows[1:]):
        child_caps = set(child.get("capabilities") or [])
        parent_caps = set(parent.get("capabilities") or [])
        if not child_caps.issubset(parent_caps):
            raise GrantResolutionError("DENY_DELEGATION_ESCALATION")

        child_scope = child.get("scope") or {}
        parent_scope = parent.get("scope") or {}
        if not isinstance(child_scope, Mapping) or not isinstance(parent_scope, Mapping):
            raise GrantResolutionError("DENY_SCOPE_MISMATCH")
        if not _scope_subset(child_scope, parent_scope):
            raise GrantResolutionError("DENY_SCOPE_MISMATCH")

        child_budget = child.get("budget") or {}
        parent_budget = parent.get("budget") or {}
        if not isinstance(child_budget, Mapping) or not isinstance(parent_budget, Mapping):
            raise GrantResolutionError("DENY_DELEGATION_ESCALATION")
        if not _budget_not_wider(child_budget, parent_budget):
            raise GrantResolutionError("DENY_DELEGATION_ESCALATION")

        child_until = child.get("valid_until")
        parent_until = parent.get("valid_until")
        if child_until is not None and parent_until is not None and _utc(child_until) > _utc(parent_until):
            raise GrantResolutionError("DENY_DELEGATION_ESCALATION")

    return ResolvedGrant(
        grant_id=grant_id,
        agent_id=leaf_agent,
        capabilities=leaf_caps,
        scope=dict(leaf_scope),
        budget=dict(leaf_budget),
        chain=tuple(chain_ids),
    )
