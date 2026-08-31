from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from grant_resolution import GrantResolutionError, resolve_grant_chain
from runtime_policy import evaluate_runtime


@dataclass(frozen=True)
class TransitionResult:
    applied: bool
    decision: dict[str, Any]
    transition_result: Any = None


def execute_guarded_transition(
    action: dict[str, Any],
    grants_by_id: dict[str, dict[str, Any]],
    leaf_grant_id: str,
    transition: Callable[[dict[str, Any]], Any],
    *,
    replay_record: dict[str, str] | None = None,
    now=None,
) -> TransitionResult:
    """ACP enforcement boundary for selected non-production transitions.

    The state-changing callback is invoked only after authoritative grant-chain
    resolution and runtime policy return an explicit allow. Any missing/invalid
    policy evidence fails closed. Production capabilities are never executed here.
    """
    capability = str(action.get("capability") or "")
    if capability.startswith("production."):
        decision = {
            "schema_version": "1.0",
            "action_id": str(action.get("action_id") or ""),
            "decision": "require_human_approval",
            "reason_code": "REQUIRE_HUMAN_PRODUCTION_APPROVAL",
            "effective_capabilities": [],
            "human_approval_required": True,
        }
        return TransitionResult(False, decision)

    try:
        grant = resolve_grant_chain(
            grants_by_id,
            leaf_grant_id,
            expected_principal_id=str(action.get("actor_id") or ""),
            now=now,
        )
    except GrantResolutionError as exc:
        decision = {
            "schema_version": "1.0",
            "action_id": str(action.get("action_id") or ""),
            "decision": "deny",
            "reason_code": exc.reason_code,
            "effective_capabilities": [],
        }
        return TransitionResult(False, decision)

    decision = evaluate_runtime(
        action,
        grant,
        replay_record=replay_record,
        now=now,
        policy_available=True,
    )
    if decision.get("decision") != "allow":
        return TransitionResult(False, decision)

    return TransitionResult(True, decision, transition(action))
