from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys

from runtime_policy import canonical_digest, evaluate_runtime

NOW = datetime(2026, 8, 31, 16, 0, tzinfo=timezone.utc)
PROJECT = "11111111-1111-4111-8111-111111111111"
RUN = "22222222-2222-4222-8222-222222222222"


def action(capability="factory.plan", *, action_id="action-runtime-test-0001", scope=None, expires_delta=600, provenance=True, budget=None):
    payload = {"intent": "runtime-test", "capability": capability}
    return {
        "schema_version": "1.0",
        "action_id": action_id,
        "requested_at": NOW.isoformat().replace("+00:00", "Z"),
        "expires_at": (NOW + timedelta(seconds=expires_delta)).isoformat().replace("+00:00", "Z"),
        "requester": {
            "agent_id": "planner-agent",
            "agent_version": "1",
            "role": "planner",
            "principal_type": "agent",
        },
        "capability": capability,
        "scope": scope or {"project_id": PROJECT, "factory_run_id": RUN},
        "provenance": {"source_type": "factory_run", "source_id": RUN} if provenance else {},
        "input_digest": canonical_digest(payload),
        "budget": budget or {"timeout_seconds": 60, "max_retries": 1, "max_cost_minor": 100},
    }


def grant(capabilities=None, scope=None, delegated=None, budget=None):
    out = {
        "capabilities": capabilities or ["factory.plan"],
        "scope": scope or {"project_id": PROJECT, "factory_run_id": RUN},
        "budget": budget or {"timeout_seconds": 120, "max_retries": 2, "max_cost_minor": 200},
    }
    if delegated is not None:
        out["delegated_capabilities"] = delegated
    return out


def expect(name, result, decision, reason):
    if result.get("decision") != decision or result.get("reason_code") != reason:
        raise AssertionError(f"{name}: expected {decision}/{reason}, got {result}")
    return {"name": name, "status": "PASS", "decision": decision, "reason_code": reason}


def main():
    results = []
    results.append(expect("allow valid action", evaluate_runtime(action(), grant(), now=NOW), "allow", "ALLOW_POLICY_MATCH"))
    results.append(expect("deny unavailable policy", evaluate_runtime(action(), None, now=NOW, policy_available=False), "deny", "DENY_POLICY_UNAVAILABLE"))
    results.append(expect("deny missing provenance", evaluate_runtime(action(provenance=False), grant(), now=NOW), "deny", "DENY_MISSING_PROVENANCE"))
    results.append(expect("deny expired action", evaluate_runtime(action(expires_delta=-1), grant(), now=NOW), "deny", "DENY_EXPIRED_ACTION"))
    results.append(expect("deny unknown capability", evaluate_runtime(action("factory.root"), grant(["factory.root"]), now=NOW), "deny", "DENY_UNKNOWN_CAPABILITY"))
    results.append(expect("deny ungranted capability", evaluate_runtime(action("qa.execute"), grant(["factory.plan"]), now=NOW), "deny", "DENY_CAPABILITY_NOT_GRANTED"))
    results.append(expect("deny scope escape", evaluate_runtime(action(scope={"project_id": "33333333-3333-4333-8333-333333333333"}), grant(), now=NOW), "deny", "DENY_SCOPE_MISMATCH"))
    results.append(expect("deny delegation escalation", evaluate_runtime(action(), grant(["factory.plan"], delegated=["factory.plan", "qa.execute"]), now=NOW), "deny", "DENY_DELEGATION_ESCALATION"))
    results.append(expect("deny budget escalation", evaluate_runtime(action(budget={"timeout_seconds": 300, "max_retries": 1, "max_cost_minor": 100}), grant(), now=NOW), "deny", "DENY_DELEGATION_ESCALATION"))
    results.append(expect("production approve requires human", evaluate_runtime(action("production.approve"), grant(["production.approve"]), now=NOW), "require_human_approval", "REQUIRE_HUMAN_PRODUCTION_APPROVAL"))
    results.append(expect("production promote requires human", evaluate_runtime(action("production.promote"), grant(["production.promote"]), now=NOW), "require_human_approval", "REQUIRE_HUMAN_PRODUCTION_APPROVAL"))

    original = action(action_id="action-runtime-replay-0001")
    replay = {original["action_id"]: original["input_digest"]}
    results.append(expect("identical replay is idempotent", evaluate_runtime(original, grant(), replay_record=replay, now=NOW), "allow", "ALLOW_POLICY_MATCH"))
    changed = dict(original)
    changed["input_digest"] = canonical_digest({"intent": "changed"})
    results.append(expect("changed replay denied", evaluate_runtime(changed, grant(), replay_record=replay, now=NOW), "deny", "DENY_REPLAY"))

    evidence = {
        "suite": "VL Agent Control Plane runtime policy V1",
        "status": "PASS",
        "runtime_module_present": True,
        "production_execution_wired": False,
        "human_production_approval_preserved": True,
        "tests": results,
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"suite": "VL Agent Control Plane runtime policy V1", "status": "FAIL", "error": str(exc)}, indent=2))
        sys.exit(1)
