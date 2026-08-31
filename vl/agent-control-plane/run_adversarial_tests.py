from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from reference_policy import evaluate

ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 8, 31, 15, 50, tzinfo=timezone.utc)
PROJECT = "11111111-1111-4111-8111-111111111111"
OTHER_PROJECT = "22222222-2222-4222-8222-222222222222"


def base_action() -> dict:
    return {
        "schema_version": "1.0",
        "action_id": "act-20260831-000001",
        "requested_at": "2026-08-31T15:49:00Z",
        "expires_at": "2026-08-31T16:49:00Z",
        "requester": {
            "agent_id": "planner",
            "agent_version": "1",
            "role": "planner",
            "principal_type": "agent",
            "delegated_by": "control-plane",
        },
        "capability": "factory.plan",
        "scope": {"project_id": PROJECT, "target_environment": "staging"},
        "provenance": {"source_type": "user_request", "source_id": "req-1"},
        "input_digest": "sha256:" + "a" * 64,
        "budget": {"timeout_seconds": 300, "max_retries": 1, "max_cost_minor": 1000},
    }


def base_grant() -> dict:
    return {
        "capabilities": ["factory.plan", "artifact.read", "release.request_approval"],
        "scope": {"project_id": PROJECT, "target_environment": "staging"},
    }


def expect(label: str, decision: dict, expected_decision: str, expected_reason: str) -> dict:
    ok = decision.get("decision") == expected_decision and decision.get("reason_code") == expected_reason
    if not ok:
        raise AssertionError(f"{label}: expected {expected_decision}/{expected_reason}, got {decision}")
    return {"test": label, "status": "PASS", "decision": decision["decision"], "reason_code": decision["reason_code"]}


def main() -> None:
    results = []

    # Positive control.
    results.append(expect("authorized_in_scope", evaluate(base_action(), base_grant(), now=NOW), "allow", "ALLOW_POLICY_MATCH"))

    action = base_action(); action["capability"] = "secrets.read_all"
    results.append(expect("unknown_capability", evaluate(action, base_grant(), now=NOW), "deny", "DENY_UNKNOWN_CAPABILITY"))

    action = base_action(); action["capability"] = "qa.execute"
    results.append(expect("ungranted_capability", evaluate(action, base_grant(), now=NOW), "deny", "DENY_CAPABILITY_NOT_GRANTED"))

    action = base_action(); action["scope"]["project_id"] = OTHER_PROJECT
    results.append(expect("scope_escape", evaluate(action, base_grant(), now=NOW), "deny", "DENY_SCOPE_MISMATCH"))

    grant = base_grant(); grant["delegated_capabilities"] = grant["capabilities"] + ["qa.execute"]
    results.append(expect("delegation_escalation", evaluate(base_action(), grant, now=NOW), "deny", "DENY_DELEGATION_ESCALATION"))

    action = base_action(); action["expires_at"] = "2026-08-31T15:00:00Z"
    results.append(expect("expired_action", evaluate(action, base_grant(), now=NOW), "deny", "DENY_EXPIRED_ACTION"))

    action = base_action()
    results.append(expect("replay", evaluate(action, base_grant(), seen_action_ids={action["action_id"]}, now=NOW), "deny", "DENY_REPLAY"))

    action = base_action(); action["provenance"] = {}
    results.append(expect("missing_provenance", evaluate(action, base_grant(), now=NOW), "deny", "DENY_MISSING_PROVENANCE"))

    action = base_action(); action["capability"] = "production.approve"; action["scope"]["target_environment"] = "production"
    grant = base_grant(); grant["capabilities"].append("production.approve"); grant["scope"]["target_environment"] = "production"
    decision = evaluate(action, grant, now=NOW)
    results.append(expect("production_approval_requires_human", decision, "require_human_approval", "REQUIRE_HUMAN_PRODUCTION_APPROVAL"))
    if decision.get("human_approval_required") is not True:
        raise AssertionError("production approval decision must explicitly require human approval")

    # Contract invariants must remain machine-readable and fail closed.
    action_schema = json.loads((ROOT / "action-envelope.schema.json").read_text())
    decision_schema = json.loads((ROOT / "policy-decision.schema.json").read_text())
    required = set(action_schema.get("required", []))
    for field in {"action_id", "expires_at", "capability", "scope", "provenance", "budget"}:
        if field not in required:
            raise AssertionError(f"action schema no longer requires {field}")
    reasons = set(decision_schema["properties"]["reason_code"]["enum"])
    for reason in {
        "DENY_UNKNOWN_CAPABILITY",
        "DENY_CAPABILITY_NOT_GRANTED",
        "DENY_SCOPE_MISMATCH",
        "DENY_DELEGATION_ESCALATION",
        "DENY_EXPIRED_ACTION",
        "DENY_REPLAY",
        "DENY_MISSING_PROVENANCE",
        "DENY_POLICY_UNAVAILABLE",
        "REQUIRE_HUMAN_PRODUCTION_APPROVAL",
    }:
        if reason not in reasons:
            raise AssertionError(f"policy decision schema missing stable reason {reason}")

    evidence = {
        "suite": "vl-agent-control-plane-v1-adversarial",
        "status": "PASS",
        "runtime_enforcement": False,
        "note": "Reference contract evaluator only; production runtime enforcement remains outstanding under issue #95.",
        "tests": results,
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
