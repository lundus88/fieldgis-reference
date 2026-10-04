#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHAIN = ROOT / "vl/lom-canonical-compliance/canonical-chain.json"
ACTIONS = ROOT / "vl/lom-operational-safety/action-registry.json"
SNAPSHOT = Path(__file__).with_name("policy-data.json")

EXPECTED_AUTHORITY = {
    "autonomous_ceiling": "PREPARE_PR",
    "production_authority": "HUMAN_ONLY",
    "protected_main_merge": "HUMAN_ONLY",
    "self_approval": "FORBIDDEN",
    "missing_evidence": "HOLD",
    "unknown_authority": "HOLD",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_projection() -> dict[str, Any]:
    chain = json.loads(CHAIN.read_text(encoding="utf-8"))
    actions = json.loads(ACTIONS.read_text(encoding="utf-8"))

    if chain.get("schema") != "lom.canonical-compliance-chain/1":
        raise ValueError("CANONICAL_CHAIN_SCHEMA_INVALID")
    if chain.get("status") != "DEVELOPMENT_NON_PRODUCTION":
        raise ValueError("CANONICAL_CHAIN_STATUS_INVALID")

    authority = chain.get("authority") or {}
    for key, expected in EXPECTED_AUTHORITY.items():
        if authority.get(key) != expected:
            raise ValueError(f"AUTHORITY_INVARIANT_WEAKENED:{key}")

    if actions.get("schema") != "lom.action-registry/1":
        raise ValueError("ACTION_REGISTRY_SCHEMA_INVALID")
    if actions.get("default_decision") != "DENY":
        raise ValueError("ACTION_REGISTRY_DEFAULT_DENY_REQUIRED")
    if actions.get("production_locked") is not True:
        raise ValueError("PRODUCTION_LOCK_REQUIRED")

    human_only = sorted(set(str(x) for x in (actions.get("human_only_actions") or []) if str(x)))
    if not human_only:
        raise ValueError("HUMAN_ONLY_ACTIONS_REQUIRED")

    bounded = []
    for item in actions.get("actions") or []:
        if not isinstance(item, dict):
            raise ValueError("ACTION_RECORD_INVALID")
        action_id = str(item.get("action_id") or "").strip()
        capability_id = str(item.get("capability_id") or "").strip()
        if not action_id or not capability_id:
            raise ValueError("ACTION_IDENTITY_INVALID")
        if item.get("non_production_only") is not True:
            raise ValueError(f"BOUNDED_ACTION_MUST_BE_NON_PRODUCTION:{action_id}")
        bounded.append({
            "action_id": action_id,
            "capability_id": capability_id,
            "max_risk": item.get("max_risk"),
            "reversible_required": bool(item.get("reversible_required")),
        })
    bounded.sort(key=lambda x: x["action_id"])

    source_payload = {
        "authority": dict(sorted(authority.items())),
        "human_only_actions": human_only,
        "bounded_actions": bounded,
    }

    projection = {
        "schema": "lom.policy-projection/1",
        "status": "DEVELOPMENT_NON_PRODUCTION",
        "policy_role": "VERIFIER_ONLY",
        "authority": dict(sorted(authority.items())),
        "human_only_actions": human_only,
        "bounded_actions": bounded,
        "default_decision": "HOLD",
        "production_locked": True,
        "execution_authority": "NONE",
        "live_policy_mutation": "DISABLED",
        "opa_network_runtime": "DISABLED",
        "sources": {
            "canonical_chain": {
                "path": str(CHAIN.relative_to(ROOT)),
            },
            "action_registry": {
                "path": str(ACTIONS.relative_to(ROOT)),
            },
            "canonical_input_digest": sha256_json(source_payload),
        },
    }
    projection["projection_digest"] = sha256_json(projection)
    return {"lom": projection}


def check_snapshot(expected: dict[str, Any]) -> None:
    actual = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if actual != expected:
        raise SystemExit("FAIL: POLICY_DATA_DRIFT")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    projection = build_projection()
    if args.check:
        check_snapshot(projection)
        print("LOM POLICY DATA: PASS")
        print("POLICY ROLE: VERIFIER_ONLY")
        print("AUTONOMOUS CEILING: PREPARE_PR")
        return 0

    text = json.dumps(projection, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
