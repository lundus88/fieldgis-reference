from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

from action_registry import ActionRegistry
from delegation import validate_actor_separation, validate_delegation
from evidence_replay import ReplayGuard, validate_evidence

ROOT = Path(__file__).resolve().parent
SCENARIOS_PATH = ROOT / "red-team-scenarios.json"

INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"reveal\s+secret",
    r"production\.approve",
    r"merge\s+protected",
    r"INJECT_MARKER_42",
)


def _load_lom5_runtime():
    path = ROOT.parent / "lom-5-operational-maturity" / "runtime.py"
    spec = importlib.util.spec_from_file_location("lom5_runtime_for_redteam", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("LOM5_RUNTIME_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LOM5 = _load_lom5_runtime()


def inspect_untrusted_text(text: str, canary: str | None = None) -> dict[str, str]:
    """Reference boundary check for synthetic hostile tool/model output.

    This is intentionally conservative and is not claimed as a universal prompt-
    injection detector. It exists to prove that known hostile markers and secret
    canaries fail closed before downstream autonomous handling.
    """
    if not isinstance(text, str) or not text.strip():
        return {"decision": "HOLD", "reason": "UNTRUSTED_TEXT_INVALID"}
    if canary and canary in text:
        return {"decision": "HOLD", "reason": "SECRET_CANARY_EXPOSURE"}
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {"decision": "HOLD", "reason": "PROMPT_INJECTION_PATTERN"}
    if "<script" in lowered or "javascript:" in lowered:
        return {"decision": "HOLD", "reason": "ACTIVE_CONTENT_PATTERN"}
    return {"decision": "ALLOW", "reason": "NO_KNOWN_HOSTILE_MARKER"}


def validate_tool_result(result: Any) -> dict[str, str]:
    if not isinstance(result, dict):
        return {"decision": "HOLD", "reason": "TOOL_RESULT_SCHEMA_INVALID"}
    if set(result) - {"status", "evidence_ref", "payload"}:
        return {"decision": "HOLD", "reason": "TOOL_RESULT_SCHEMA_INVALID"}
    if result.get("status") not in {"PASS", "HOLD", "FAIL"}:
        return {"decision": "HOLD", "reason": "TOOL_RESULT_SCHEMA_INVALID"}
    if not isinstance(result.get("evidence_ref"), str) or not result["evidence_ref"].strip():
        return {"decision": "HOLD", "reason": "TOOL_RESULT_SCHEMA_INVALID"}
    return {"decision": "ALLOW", "reason": "TOOL_RESULT_SCHEMA_VALID"}


def verify_artifact_digest(content: str, expected_sha256: str) -> dict[str, str]:
    if not isinstance(content, str) or not isinstance(expected_sha256, str):
        return {"decision": "HOLD", "reason": "ARTIFACT_DIGEST_INPUT_INVALID"}
    actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if actual != expected_sha256:
        return {"decision": "HOLD", "reason": "ARTIFACT_DIGEST_MISMATCH"}
    return {"decision": "ALLOW", "reason": "ARTIFACT_DIGEST_VERIFIED"}


def _execute_scenario(scenario: dict[str, Any], registry: ActionRegistry) -> dict[str, str]:
    kind = scenario.get("type")
    data = scenario.get("input") or {}

    if kind == "UNTRUSTED_TEXT_INJECTION":
        return inspect_untrusted_text(data.get("text", ""), data.get("canary"))

    if kind == "SECRET_CANARY_EXFILTRATION":
        return inspect_untrusted_text(data.get("text", ""), data.get("canary"))

    if kind == "TOOL_RESULT_SCHEMA_POISONING":
        return validate_tool_result(data.get("result"))

    if kind in {"CONNECTOR_SCOPE_ESCAPE", "AUTHORITY_WIDENING"}:
        parent = {
            "environment": "NON_PRODUCTION",
            "capability_ids": ["connector.invoke:github", "cap.test.execute"],
            "risk_ceiling": "LOW",
            "expires_at_epoch": 2000,
            "max_attempts": 2,
        }
        child = dict(parent)
        if kind == "CONNECTOR_SCOPE_ESCAPE":
            child["capability_ids"] = ["connector.invoke:github", "connector.invoke:production-db"]
        else:
            child["risk_ceiling"] = "HIGH"
        return validate_delegation(parent, child, 1000)

    if kind == "STALE_EVIDENCE":
        return validate_evidence("PASS", 100, 1000, 100)

    if kind == "CONTRADICTORY_EVIDENCE":
        return validate_evidence("PASS", 950, 1000, 100, contradictory=True)

    if kind == "REPLAY_ATTACK":
        guard = ReplayGuard()
        guard.claim("run-redteam", "objective-redteam", "same-key")
        return guard.claim("run-redteam", "objective-redteam", "same-key")

    if kind == "PROVIDER_OUTAGE":
        adapter = LOM5.ProviderAdapter(
            provider_id="provider-down",
            adapter_version="1",
            capabilities=frozenset({"reasoning"}),
            healthy=False,
            credential_mode="none",
            identity_attested=True,
            retention="none",
            training="disabled",
        )
        result = LOM5.select_provider([adapter], "reasoning")
        return {"decision": result["status"], "reason": result["reason"]}

    if kind == "CORRUPTED_ARTIFACT":
        return verify_artifact_digest(data.get("content", ""), data.get("expected_sha256", ""))

    if kind == "BUDGET_EXHAUSTION":
        return LOM5.capacity_guard(
            requested_units=int(data.get("requested_units", 10)),
            available_units=int(data.get("available_units", 10)),
            budget_units=int(data.get("budget_units", 1)),
            environment="development",
        )

    if kind == "ACTOR_COLLISION":
        return validate_actor_separation("same-actor", "same-actor")

    if kind == "PRODUCTION_ACTION_ATTEMPT":
        return registry.authorize("PRODUCTION_RELEASE", "cap.test.execute", "LOW", True, True)

    if kind == "UNKNOWN_ACTION":
        return registry.authorize("ATTACKER_DEFINED_ACTION", "cap.test.execute", "LOW", True, False)

    return {"decision": "HOLD", "reason": "UNKNOWN_RED_TEAM_SCENARIO"}


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_scenarios(path: Path = SCENARIOS_PATH) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    if raw.get("schema") != "lom.red-team-chaos/1":
        raise ValueError("RED_TEAM_SCHEMA_INVALID")
    if raw.get("mode") != "NON_PRODUCTION_SIMULATION":
        raise ValueError("RED_TEAM_MODE_MUST_BE_NON_PRODUCTION")
    if raw.get("network_access") != "DISABLED" or raw.get("credential_access") != "NONE":
        raise ValueError("RED_TEAM_ISOLATION_REQUIRED")
    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("RED_TEAM_SCENARIOS_REQUIRED")
    ids = [s.get("id") for s in scenarios]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("RED_TEAM_SCENARIO_IDS_INVALID")
    return raw


def run_suite(path: Path = SCENARIOS_PATH) -> dict[str, Any]:
    contract = load_scenarios(path)
    registry = ActionRegistry.from_path(ROOT / "action-registry.json")
    results = []

    for scenario in contract["scenarios"]:
        actual = _execute_scenario(scenario, registry)
        expected_decision = scenario.get("expected_decision")
        expected_reason = scenario.get("expected_reason")
        passed = actual.get("decision") == expected_decision and actual.get("reason") == expected_reason
        results.append(
            {
                "id": scenario["id"],
                "type": scenario["type"],
                "target_control": scenario.get("target_control"),
                "passed": passed,
                "expected": {"decision": expected_decision, "reason": expected_reason},
                "actual": actual,
            }
        )

    passed_count = sum(1 for r in results if r["passed"])
    summary = {
        "schema": "lom.red-team-chaos-result/1",
        "status": "PASS" if passed_count == len(results) else "HOLD",
        "reason": "ALL_ATTACKS_FAIL_CLOSED" if passed_count == len(results) else "RED_TEAM_DEFENSE_GAP",
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "results": results,
        "production_locked": True,
        "environment": "NON_PRODUCTION",
        "network_access": "DISABLED",
        "credential_access": "NONE",
        "execution_authority": "NONE",
        "execution_performed": False,
        "autonomous_ceiling": "PREPARE_PR",
    }
    summary["evaluation_fingerprint"] = _canonical_sha256(summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run_suite(), indent=2, sort_keys=True))
