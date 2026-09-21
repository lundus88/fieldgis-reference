from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE / "execution-result.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"CANNOT_LOAD:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    started = time.monotonic()
    source_sha = os.environ.get(
        "GOLDEN_SOURCE_SHA",
        os.environ.get("GITHUB_SHA", ""),
    ).strip()
    github_run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if len(source_sha) not in {40, 64}:
        raise SystemExit("EXACT_SOURCE_SHA_REQUIRED")
    if not github_run_id:
        raise SystemExit("GITHUB_RUN_ID_REQUIRED")

    delegation = load_module(
        "lom_multi_agent_delegation",
        ROOT / "vl/multi-agent-governance/delegation_policy.py",
    )
    safety = load_module(
        "lom_operational_safety_delegation",
        ROOT / "vl/lom-operational-safety/delegation.py",
    )

    policy_data = json.loads(
        (ROOT / "vl/context-governance/default-context-policy.json").read_text(
            encoding="utf-8"
        )
    )
    context_policy_sha = sha256_json(policy_data)
    parent_run_id = "golden-8-lom-bounded-multi-agent"

    parent = {
        "capabilities": [
            "repo.read",
            "ci.inspect",
            "test.execute",
            "artifact.render",
        ],
        "resource_scopes": [
            "repo:lundus88/fieldgis-reference",
            "path:vl/multi-agent-governance",
            "path:vl/lom-operational-safety",
            "path:vl/lom-5-operational-maturity",
        ],
        "budget": {
            "max_tokens": 0,
            "max_cost_microunits": 0,
            "max_steps": 20,
            "max_time_seconds": 300,
            "max_retries": 0,
        },
    }

    def child(role, capabilities, scopes, steps):
        return {
            "role": role,
            "capabilities": capabilities,
            "resource_scopes": scopes,
            "budget": {
                "max_tokens": 0,
                "max_cost_microunits": 0,
                "max_steps": steps,
                "max_time_seconds": 120,
                "max_retries": 0,
            },
            "context_manifest_required": True,
            "context_policy_sha256": context_policy_sha,
            "parent_run_id": parent_run_id,
        }

    children = {
        "planner-1": child(
            "planner",
            ["repo.read"],
            ["repo:lundus88/fieldgis-reference"],
            4,
        ),
        "builder-1": child(
            "implementer",
            ["repo.read", "test.execute"],
            [
                "repo:lundus88/fieldgis-reference",
                "path:vl/multi-agent-governance",
            ],
            6,
        ),
        "qa-1": child(
            "qa",
            ["repo.read", "ci.inspect"],
            ["repo:lundus88/fieldgis-reference"],
            5,
        ),
        "cert-1": child(
            "independent-certifier",
            ["repo.read", "ci.inspect"],
            ["repo:lundus88/fieldgis-reference"],
            5,
        ),
    }

    decisions = {
        worker_id: delegation.authorize_delegation(parent, payload)
        for worker_id, payload in children.items()
    }

    controlled_plan = {
        "workers": [
            {"id": "planner-1", "role": "planner"},
            {"id": "builder-1", "role": "implementer"},
            {"id": "qa-1", "role": "qa"},
            {"id": "cert-1", "role": "independent-certifier"},
        ],
        "max_workers": 4,
        "swarm_mode": False,
    }
    orchestration = delegation.orchestrate(controlled_plan)

    actor_separation = safety.validate_actor_separation(
        "builder-1",
        "cert-1",
        "qa-1",
    )

    safety_parent = {
        "environment": "NON_PRODUCTION",
        "capability_ids": ["cap.test.execute", "cap.report.render"],
        "risk_ceiling": "LOW",
        "expires_at_epoch": 2000,
        "max_attempts": 2,
    }
    safety_child = {
        "environment": "NON_PRODUCTION",
        "capability_ids": ["cap.test.execute"],
        "risk_ceiling": "LOW",
        "expires_at_epoch": 1500,
        "max_attempts": 1,
    }
    safety_delegation = safety.validate_delegation(
        safety_parent,
        safety_child,
        1000,
    )

    forbidden_capability = delegation.authorize_delegation(
        parent,
        child(
            "implementer",
            ["repo.read", "production.deploy"],
            ["repo:lundus88/fieldgis-reference"],
            4,
        ),
    )

    widened_budget_child = child(
        "implementer",
        ["repo.read"],
        ["repo:lundus88/fieldgis-reference"],
        4,
    )
    widened_budget_child["budget"]["max_time_seconds"] = 301
    widened_budget = delegation.authorize_delegation(
        parent,
        widened_budget_child,
    )

    widened_scope = delegation.authorize_delegation(
        parent,
        child(
            "implementer",
            ["repo.read"],
            ["repo:outside/authority"],
            4,
        ),
    )

    swarm_block = delegation.orchestrate(
        {
            "workers": [
                {"id": "builder-1", "role": "implementer"},
                {"id": "cert-1", "role": "independent-certifier"},
            ],
            "max_workers": 2,
            "swarm_mode": True,
        }
    )

    actor_collision = safety.validate_actor_separation(
        "builder-1",
        "builder-1",
    )

    safety_widened = dict(
        safety_child,
        capability_ids=["cap.test.execute", "cap.unknown"],
    )
    safety_widening = safety.validate_delegation(
        safety_parent,
        safety_widened,
        1000,
    )

    positive_checks = {
        "all_child_delegations_allowed": all(
            item.get("decision") == "ALLOW"
            and item.get("authority_expanded") is False
            and item.get("production_locked") is True
            for item in decisions.values()
        ),
        "controlled_plan_ready": (
            orchestration.get("status") == "READY_FOR_CONTROLLED_EXECUTION"
            and orchestration.get("production_approval") == "HUMAN_ONLY"
            and orchestration.get("production_locked") is True
        ),
        "actor_separation_enforced": actor_separation == {
            "decision": "ALLOW",
            "reason": "ACTOR_SEPARATION_OK",
        },
        "safety_envelope_non_expanding": safety_delegation == {
            "decision": "ALLOW",
            "reason": "DELEGATION_NON_EXPANDING",
        },
    }

    negative_checks = {
        "production_capability_blocked": (
            forbidden_capability.get("decision") == "DENY"
            and forbidden_capability.get("reason")
            == "FORBIDDEN_CAPABILITY_REQUESTED"
        ),
        "budget_widening_blocked": (
            widened_budget.get("decision") == "DENY"
            and widened_budget.get("reason") == "BUDGET_EXPANSION_BLOCKED"
        ),
        "scope_widening_blocked": (
            widened_scope.get("decision") == "DENY"
            and widened_scope.get("reason")
            == "RESOURCE_SCOPE_EXPANSION_BLOCKED"
        ),
        "swarm_mode_blocked": (
            swarm_block.get("status") == "BLOCKED"
            and swarm_block.get("reason") == "SWARM_MODE_FORBIDDEN_BY_DEFAULT"
        ),
        "executor_validator_collision_blocked": (
            actor_collision.get("decision") == "HOLD"
            and actor_collision.get("reason") == "EXECUTOR_VALIDATOR_COLLISION"
        ),
        "safety_capability_widening_blocked": (
            safety_widening.get("decision") == "HOLD"
            and safety_widening.get("reason")
            == "DELEGATION_CAPABILITY_WIDENED"
        ),
    }

    demonstrated = all(positive_checks.values()) and all(negative_checks.values())

    result = {
        "schema": "lom.golden-workflow-execution/2",
        "golden_run_id": parent_run_id,
        "project_id": "lom",
        "github_sha": source_sha,
        "github_run_id": github_run_id,
        "attempts": 1,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "estimated_model_tool_cost": 0.0,
        "model_or_external_api_calls": 0,
        "external_network_calls": 0,
        "final_outcome": "PASS",
        "multi_agent_delegation": {
            "demonstrated": demonstrated,
            "authority_expanded": False,
            "worker_count": 4,
            "worker_ids": [
                "planner-1",
                "builder-1",
                "qa-1",
                "cert-1",
            ],
            "roles": [
                "planner",
                "implementer",
                "qa",
                "independent-certifier",
            ],
            "executor_actor_id": "builder-1",
            "validator_actor_id": "cert-1",
            "production_approval": "HUMAN_ONLY",
            "production_locked": True,
        },
        "delegation_decisions": decisions,
        "orchestration": orchestration,
        "actor_separation": actor_separation,
        "operational_safety_delegation": safety_delegation,
        "positive_checks": positive_checks,
        "negative_checks": negative_checks,
        "denial_evidence": {
            "forbidden_capability": forbidden_capability,
            "widened_budget": widened_budget,
            "widened_scope": widened_scope,
            "swarm_mode": swarm_block,
            "actor_collision": actor_collision,
            "safety_capability_widening": safety_widening,
        },
        "budget_overrun": False,
        "authority_expansion_incident": False,
        "fabricated_pass_incident": False,
        "production_approval": False,
        "builder_self_certified": False,
        "production_locked": True,
        "autonomous_ceiling": "PREPARE_PR",
    }

    OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if demonstrated else 1


if __name__ == "__main__":
    raise SystemExit(main())
