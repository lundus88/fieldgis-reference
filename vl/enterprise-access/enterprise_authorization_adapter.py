from __future__ import annotations

from typing import Any, Mapping

from authorize_workspace_action import decide as decide_workspace_action
from policy_inheritance import PolicyError, authorize_data_access, derive_effective_policy
from session_audit_visibility import SessionContext, build_audit_event


def authorize_with_audit(
    *,
    enterprise_policy: dict[str, Any],
    membership_snapshot: dict[str, Any],
    request: dict[str, Any],
    parent_data_policy: Mapping[str, Any],
    child_data_policy: Mapping[str, Any],
    session: SessionContext,
    occurred_at: str,
) -> dict[str, Any]:
    """Return fail-closed authorization decision plus redacted audit event.

    Authority remains sourced from the existing workspace/RBAC + ACP decision.
    Inherited data policy may only narrow that result. This adapter never executes
    the requested action and never creates production authority.
    """
    policy_id = str(enterprise_policy.get("policy_id") or "unknown")
    policy_version = str(enterprise_policy.get("version") or "unknown")
    capability = str(request.get("capability") or "")
    project_id = str(request.get("project_id") or "")
    classification = str(request.get("data_classification") or "internal")
    retention = str(request.get("retention_profile") or "standard")

    if session.actor_id != str(request.get("user_id") or ""):
        return _deny_with_audit(
            request=request,
            session=session,
            policy_id=policy_id,
            policy_version=policy_version,
            occurred_at=occurred_at,
            reason="DENY_SESSION_ACTOR_MISMATCH",
        )
    if session.workspace_id != str(request.get("workspace_id") or ""):
        return _deny_with_audit(
            request=request,
            session=session,
            policy_id=policy_id,
            policy_version=policy_version,
            occurred_at=occurred_at,
            reason="DENY_SESSION_WORKSPACE_MISMATCH",
        )
    if session.project_id not in (None, project_id):
        return _deny_with_audit(
            request=request,
            session=session,
            policy_id=policy_id,
            policy_version=policy_version,
            occurred_at=occurred_at,
            reason="DENY_SESSION_PROJECT_MISMATCH",
        )

    workspace_decision = decide_workspace_action(enterprise_policy, membership_snapshot, request)
    if workspace_decision.get("decision") != "allow":
        return _result_with_audit(
            request=request,
            session=session,
            policy_id=policy_id,
            policy_version=policy_version,
            occurred_at=occurred_at,
            decision=str(workspace_decision.get("decision") or "deny"),
            reason=str(workspace_decision.get("reason_code") or "DENY_ENTERPRISE_ACCESS"),
            workspace_decision=workspace_decision,
            data_decision=None,
        )

    try:
        effective = derive_effective_policy(parent_data_policy, child_data_policy)
    except PolicyError as exc:
        return _result_with_audit(
            request=request,
            session=session,
            policy_id=policy_id,
            policy_version=policy_version,
            occurred_at=occurred_at,
            decision="deny",
            reason="DENY_POLICY_INHERITANCE_INVALID",
            workspace_decision=workspace_decision,
            data_decision={"decision": "deny", "reason": str(exc)},
        )

    data_decision = authorize_data_access(
        effective,
        project_id=project_id,
        classification=classification,
        retention_profile=retention,
        capability=capability,
    )
    if data_decision.get("decision") != "allow":
        return _result_with_audit(
            request=request,
            session=session,
            policy_id=policy_id,
            policy_version=policy_version,
            occurred_at=occurred_at,
            decision="deny",
            reason=f"DENY_DATA_POLICY_{data_decision.get('reason', 'UNKNOWN')}",
            workspace_decision=workspace_decision,
            data_decision=data_decision,
        )

    return _result_with_audit(
        request=request,
        session=session,
        policy_id=policy_id,
        policy_version=policy_version,
        occurred_at=occurred_at,
        decision="allow",
        reason="ALLOW_ENTERPRISE_ACP_AND_DATA_POLICY",
        workspace_decision=workspace_decision,
        data_decision=data_decision,
    )


def _deny_with_audit(*, request, session, policy_id, policy_version, occurred_at, reason):
    return _result_with_audit(
        request=request,
        session=session,
        policy_id=policy_id,
        policy_version=policy_version,
        occurred_at=occurred_at,
        decision="deny",
        reason=reason,
        workspace_decision=None,
        data_decision=None,
    )


def _result_with_audit(
    *,
    request: dict[str, Any],
    session: SessionContext,
    policy_id: str,
    policy_version: str,
    occurred_at: str,
    decision: str,
    reason: str,
    workspace_decision: dict[str, Any] | None,
    data_decision: dict[str, Any] | None,
) -> dict[str, Any]:
    audit_outcome = "ALLOW" if decision == "allow" else "HOLD" if decision == "require_human_approval" else "DENY"
    audit = build_audit_event(
        session=session,
        action=str(request.get("capability") or "unknown"),
        policy_id=policy_id,
        policy_version=policy_version,
        outcome=audit_outcome,
        reason=reason,
        resource_scope=f"workspace:{request.get('workspace_id')}|project:{request.get('project_id')}",
        occurred_at=occurred_at,
        metadata={
            "workspace_reason": (workspace_decision or {}).get("reason_code"),
            "data_reason": (data_decision or {}).get("reason"),
            "decision_sha256": (workspace_decision or {}).get("decision_sha256"),
        },
    )
    return {
        "schema": "vl.enterprise-authorization-adapter/1",
        "decision": decision,
        "reason": reason,
        "workspace_decision": workspace_decision,
        "data_decision": data_decision,
        "audit_event": audit,
        "direct_execution_authority": False,
        "production_authority": False,
    }
