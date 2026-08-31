from __future__ import annotations

from datetime import datetime, timezone

from grant_resolution import GrantResolutionError, resolve_grant

NOW = datetime(2026, 8, 31, 16, 0, tzinfo=timezone.utc)

ROOT = {
    "grant_id": "g-root",
    "agent_id": "planner-root",
    "capabilities": ["factory.plan", "factory.enqueue", "artifact.read"],
    "scope": {"project_id": "11111111-1111-1111-1111-111111111111", "target_environment": "staging"},
    "budget": {"timeout_seconds": 600, "max_retries": 3, "max_cost_minor": 1000},
    "valid_until": "2026-09-01T00:00:00Z",
    "revoked_at": None,
    "delegated_from_grant_id": None,
}

CHILD = {
    "grant_id": "g-child",
    "agent_id": "planner-child",
    "capabilities": ["factory.plan", "artifact.read"],
    "scope": {"project_id": "11111111-1111-1111-1111-111111111111"},
    "budget": {"timeout_seconds": 300, "max_retries": 1, "max_cost_minor": 500},
    "valid_until": "2026-08-31T23:00:00Z",
    "revoked_at": None,
    "delegated_from_grant_id": "g-root",
}


def expect_error(name, rows, reason, *, expected_agent_id="planner-child"):
    try:
        resolve_grant("g-child", rows, expected_agent_id=expected_agent_id, now=NOW)
    except GrantResolutionError as exc:
        assert exc.reason_code == reason, (name, exc.reason_code, reason)
        return True
    raise AssertionError(f"{name}: expected {reason}")


def main():
    checks = {}

    rows = {"g-root": dict(ROOT), "g-child": dict(CHILD)}
    resolved = resolve_grant("g-child", rows, expected_agent_id="planner-child", now=NOW)
    checks["valid_restrictive_delegation"] = (
        resolved.chain == ("g-child", "g-root")
        and resolved.capabilities == frozenset({"factory.plan", "artifact.read"})
        and resolved.scope == {"project_id": "11111111-1111-1111-1111-111111111111"}
    )

    bad = dict(CHILD)
    bad["capabilities"] = ["factory.plan", "qa.execute"]
    checks["capability_escalation_denied"] = expect_error(
        "capability_escalation", {"g-root": dict(ROOT), "g-child": bad}, "DENY_DELEGATION_ESCALATION"
    )

    bad = dict(CHILD)
    bad["scope"] = {"project_id": "22222222-2222-2222-2222-222222222222"}
    checks["scope_escape_denied"] = expect_error(
        "scope_escape", {"g-root": dict(ROOT), "g-child": bad}, "DENY_SCOPE_MISMATCH"
    )

    bad = dict(CHILD)
    bad["budget"] = {"timeout_seconds": 700, "max_retries": 1, "max_cost_minor": 500}
    checks["budget_escalation_denied"] = expect_error(
        "budget_escalation", {"g-root": dict(ROOT), "g-child": bad}, "DENY_DELEGATION_ESCALATION"
    )

    bad = dict(CHILD)
    bad["valid_until"] = "2026-09-02T00:00:00Z"
    checks["expiry_extension_denied"] = expect_error(
        "expiry_extension", {"g-root": dict(ROOT), "g-child": bad}, "DENY_DELEGATION_ESCALATION"
    )

    bad = dict(CHILD)
    bad["revoked_at"] = "2026-08-31T15:00:00Z"
    checks["revoked_grant_denied"] = expect_error(
        "revoked", {"g-root": dict(ROOT), "g-child": bad}, "DENY_POLICY_UNAVAILABLE"
    )

    bad = dict(CHILD)
    bad["valid_until"] = "2026-08-31T15:59:59Z"
    checks["expired_grant_denied"] = expect_error(
        "expired", {"g-root": dict(ROOT), "g-child": bad}, "DENY_EXPIRED_ACTION"
    )

    cycle_root = dict(ROOT)
    cycle_root["delegated_from_grant_id"] = "g-child"
    checks["delegation_cycle_denied"] = expect_error(
        "cycle", {"g-root": cycle_root, "g-child": dict(CHILD)}, "DENY_DELEGATION_ESCALATION"
    )

    checks["agent_identity_mismatch_denied"] = expect_error(
        "identity_mismatch", {"g-root": dict(ROOT), "g-child": dict(CHILD)}, "DENY_SCOPE_MISMATCH", expected_agent_id="other-agent"
    )

    checks["missing_parent_denied"] = expect_error(
        "missing_parent", {"g-child": dict(CHILD)}, "DENY_POLICY_UNAVAILABLE"
    )

    failed = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "1.0",
        "suite": "agent-control-plane-grant-resolution",
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "production_applied": False,
    }
    print(result)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
