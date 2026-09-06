#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


class EnterpriseAccessError(ValueError):
    pass


def _canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != "vl.enterprise-access-policy/1":
        raise EnterpriseAccessError("unsupported policy schema")
    if policy.get("default_decision") != "deny":
        raise EnterpriseAccessError("default_decision must be deny")
    roles = policy.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise EnterpriseAccessError("roles are required")
    for required in ("owner", "admin", "builder", "reviewer", "auditor", "viewer"):
        if required not in roles or not isinstance(roles[required], list):
            raise EnterpriseAccessError(f"missing required role: {required}")
    forbidden = set(policy.get("never_role_derived_capabilities") or [])
    for role, caps in roles.items():
        overlap = forbidden.intersection(caps)
        if overlap:
            raise EnterpriseAccessError(f"role {role} contains forbidden role-derived capability")
    approval = policy.get("production_approval") or {}
    if approval.get("human_only") is not True or approval.get("explicit_grant_required") is not True:
        raise EnterpriseAccessError("production approval must remain explicit and human-only")
    acp = policy.get("acp_integration") or {}
    if acp.get("enterprise_layer_may_only_narrow") is not True or acp.get("direct_execution_authority") is not False:
        raise EnterpriseAccessError("enterprise layer must only narrow ACP authority")
    if (policy.get("audit") or {}).get("record_secret_values") is not False:
        raise EnterpriseAccessError("secret values must never be recorded")


def _membership(snapshot: dict[str, Any], workspace_id: str, project_id: str, user_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    workspace = next((x for x in snapshot.get("workspace_memberships", []) if x.get("workspace_id") == workspace_id and x.get("user_id") == user_id), None)
    project = next((x for x in snapshot.get("project_memberships", []) if x.get("workspace_id") == workspace_id and x.get("project_id") == project_id and x.get("user_id") == user_id), None)
    return workspace, project


def decide(policy: dict[str, Any], snapshot: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    required = ("user_id", "principal_type", "workspace_id", "project_id", "capability", "acp_capabilities")
    missing = [k for k in required if request.get(k) in (None, "")]
    if missing:
        return _decision(policy, request, "deny", "DENY_MISSING_CONTEXT", {"missing": missing})

    user_id = str(request["user_id"])
    workspace_id = str(request["workspace_id"])
    project_id = str(request["project_id"])
    capability = str(request["capability"])
    principal_type = str(request["principal_type"])
    acp_caps = set(request.get("acp_capabilities") or [])

    workspace, project = _membership(snapshot, workspace_id, project_id, user_id)
    if not workspace or workspace.get("status") != "active":
        return _decision(policy, request, "deny", "DENY_WORKSPACE_MEMBERSHIP")
    if not project or project.get("status") != "active":
        return _decision(policy, request, "deny", "DENY_PROJECT_MEMBERSHIP")

    role = str(project.get("role") or workspace.get("role") or "")
    role_caps = set((policy.get("roles") or {}).get(role) or [])
    if not role_caps and capability != "production.approve":
        return _decision(policy, request, "deny", "DENY_UNKNOWN_ROLE", {"role": role})

    # Enterprise identity/RBAC is never an authority source. The action must also
    # already exist in the effective ACP capability set; enterprise policy may only narrow it.
    if capability not in acp_caps:
        return _decision(policy, request, "deny", "DENY_ACP_CAPABILITY_NOT_GRANTED")

    forbidden = set(policy.get("never_role_derived_capabilities") or [])
    if capability == "production.approve":
        if principal_type != "human":
            return _decision(policy, request, "deny", "DENY_PRODUCTION_APPROVAL_NON_HUMAN")
        explicit = request.get("explicit_production_approval_grant") is True
        if not explicit:
            return _decision(policy, request, "deny", "DENY_EXPLICIT_APPROVAL_GRANT_REQUIRED")
        if (policy.get("production_approval") or {}).get("separation_of_duties") is True:
            built_projects = set(request.get("built_project_ids") or [])
            if project_id in built_projects:
                return _decision(policy, request, "deny", "DENY_APPROVER_BUILDER_CONFLICT")
        return _decision(policy, request, "allow", "ALLOW_EXPLICIT_HUMAN_PRODUCTION_APPROVAL", {"role": role})

    if capability in forbidden:
        return _decision(policy, request, "deny", "DENY_NEVER_ROLE_DERIVED_CAPABILITY")
    if capability not in role_caps:
        return _decision(policy, request, "deny", "DENY_ROLE_CAPABILITY", {"role": role})

    requested_class = str(request.get("data_classification") or "internal")
    allowed_classes = set(project.get("data_classifications") or [])
    if requested_class == "restricted" and "restricted" not in allowed_classes:
        return _decision(policy, request, "deny", "DENY_RESTRICTED_DATA_SCOPE")

    connector = request.get("connector")
    if capability.startswith("connector.invoke:") or connector:
        connector = str(connector or capability.split(":", 1)[-1])
        scopes = set(project.get("connector_scopes") or [])
        if connector not in scopes:
            return _decision(policy, request, "deny", "DENY_CONNECTOR_SCOPE", {"connector": connector})
        if request.get("ambient_credentials") is True:
            return _decision(policy, request, "deny", "DENY_AMBIENT_CREDENTIALS")
        if request.get("paid_or_high_impact") is True and request.get("human_action_approval") is not True:
            return _decision(policy, request, "require_human_approval", "REQUIRE_HUMAN_HIGH_IMPACT_CONNECTOR_APPROVAL")

    retention = str(request.get("retention_profile") or project.get("retention_profile") or "standard")
    permitted_retention = set(project.get("retention_profiles") or [project.get("retention_profile") or "standard"])
    if retention not in permitted_retention:
        return _decision(policy, request, "deny", "DENY_RETENTION_POLICY_MISMATCH")

    return _decision(policy, request, "allow", "ALLOW_WORKSPACE_PROJECT_ROLE_AND_ACP", {"role": role})


def _decision(policy: dict[str, Any], request: dict[str, Any], decision: str, reason: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "schema": "vl.enterprise-access-decision/1",
        "decision": decision,
        "reason_code": reason,
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("version"),
        "actor_id": request.get("user_id"),
        "workspace_id": request.get("workspace_id"),
        "project_id": request.get("project_id"),
        "capability": request.get("capability"),
        "request_sha256": _canonical_sha({k: v for k, v in request.items() if k not in {"credential", "secret", "token"}}),
        "secret_values_recorded": False,
        "direct_execution_authority": False,
    }
    if extra:
        out["evidence"] = extra
    out["decision_sha256"] = _canonical_sha(out)
    return out


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: authorize_workspace_action.py <policy.json> <snapshot.json> <request.json>", file=sys.stderr)
        return 2
    try:
        policy = json.loads(Path(sys.argv[1]).read_text())
        snapshot = json.loads(Path(sys.argv[2]).read_text())
        request = json.loads(Path(sys.argv[3]).read_text())
        result = decide(policy, snapshot, request)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["decision"] == "allow" else 3
    except Exception as exc:
        print(f"ENTERPRISE ACCESS: FAIL - {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
