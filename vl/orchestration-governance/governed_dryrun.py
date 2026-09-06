#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, rel: str):
    path = ROOT / rel
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {rel}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_dryrun() -> dict[str, Any]:
    context = load_module("ctx_gateway", "vl/context-governance/pre_model_invocation.py")
    routing = load_module("model_route", "vl/model-governance/route_model.py")
    completion = load_module("completion_validator", "vl/completion-governance/independent_validator.py")
    remediation = load_module("remediation_policy", "vl/remediation-governance/remediation_policy.py")
    connector = load_module("connector_policy", "vl/connector-governance/connector_policy.py")
    execution = load_module("execution_pool", "vl/execution-governance/execution_pool_policy.py")
    delegation = load_module("delegation_policy", "vl/multi-agent-governance/delegation_policy.py")

    context_payload = context.build_pre_model_payload(
        policy_path=ROOT / "vl/context-governance/default-context-policy.json",
        resources=[
            {"resource_type": "repo_path", "resource": "src/app.ts", "data_class": "source_code", "content": "SAFE_SOURCE"},
            {"resource_type": "repo_path", "resource": ".env", "data_class": "secret", "content": "NEVER_FORWARD_SECRET"},
        ],
        task={"kind": "code_generation", "instruction": "dry-run only"},
    )
    encoded_context = json.dumps(context_payload, sort_keys=True)
    assert "SAFE_SOURCE" in encoded_context
    assert "NEVER_FORWARD_SECRET" not in encoded_context
    assert context_payload["raw_candidates_forwarded"] is False

    registry = json.loads((ROOT / "vl/model-governance/model-registry.json").read_text())
    route = routing.route_model(registry, {
        "task_class": "code_generation",
        "data_class": "proprietary_dataset",
        "input_tokens": 2000,
        "output_tokens": 1000,
        "cost_ceiling": 10.0,
        "autonomy_horizon": 2,
        "max_retention": "none",
    })
    assert route["production_locked"] is True

    app_sha = "a" * 64
    source_sha = "b" * 64
    artifact_sha = "c" * 64
    inventory = {
        "schema": "vl.acceptance-inventory/1",
        "app_spec_sha256": app_sha,
        "source_sha256": source_sha,
        "items": [{
            "requirement_id": "R1",
            "description": "dry-run acceptance evidence",
            "required": True,
            "accepted_evidence_types": ["test"],
        }],
    }
    evidence = {
        "schema": "vl.acceptance-evidence/1",
        "app_spec_sha256": app_sha,
        "source_sha256": source_sha,
        "artifact_sha256": artifact_sha,
        "evidence": [{
            "requirement_id": "R1",
            "evidence_type": "test",
            "state": "PASS",
            "evidence_digest": "dryrun-evidence-digest",
        }],
    }
    completion_decision = completion.validate_completion(inventory, evidence)
    assert completion_decision["status"] == "PASS"
    assert completion_decision["builder_self_report_trusted"] is False

    remediation_grant = {
        "capabilities": ["pr.inspect", "pr.remediate", "ci.inspect", "ci.repair", "merge.prepare"],
        "protected_branches": ["main"],
    }
    merge_prepare = remediation.authorize({"capability": "merge.prepare", "target_branch": "main"}, remediation_grant)
    merge_execute = remediation.authorize({"capability": "merge.execute", "target_branch": "main"}, remediation_grant)
    assert merge_prepare["decision"] == "ALLOW" and merge_prepare["authority"] == "recommendation_only"
    assert merge_execute["decision"] == "DENY"

    connector_profile = {
        "id": "fixture-readonly",
        "version": "1",
        "status": "certified",
        "ambient_credentials": False,
        "allowed_operations": ["read", "write"],
        "resource_scopes": ["workspace/demo"],
        "high_impact_operations": ["write"],
        "paid_operations": [],
    }
    connector_grant = {"capabilities": ["connector.invoke:fixture-readonly"]}
    connector_read = connector.authorize_connector_call(
        connector_profile,
        {"operation": "read", "resource": "workspace/demo/project"},
        connector_grant,
    )
    connector_write = connector.authorize_connector_call(
        connector_profile,
        {"operation": "write", "resource": "workspace/demo/project", "human_approval": False},
        connector_grant,
    )
    assert connector_read["decision"] == "ALLOW"
    assert connector_write["decision"] == "DENY" and connector_write["reason"] == "HUMAN_APPROVAL_REQUIRED"

    pool = {
        "pool_id": "sandbox-pool-1",
        "profile_version": "1",
        "image_digest": "sha256:fixture",
        "network_policy": "egress-deny",
        "cpu_limit": 2,
        "memory_mb_limit": 2048,
        "status": "certified",
        "ambient_production_credentials": False,
        "allowed_capabilities": ["qa.execute"],
    }
    pool_decision = execution.authorize_execution(pool, {
        "capability": "qa.execute", "cpu": 1, "memory_mb": 1024, "network_policy": "egress-deny"
    })
    attestation = execution.attest_artifact(pool, artifact_sha)
    assert pool_decision["decision"] == "ALLOW"
    assert attestation["promotable"] is True and attestation["production_locked"] is True

    parent = {
        "capabilities": ["qa.execute", "artifact.read"],
        "resource_scopes": ["workspace/demo"],
        "budget": {"max_tokens": 10000, "max_cost_microunits": 1000, "max_steps": 10},
    }
    child = {
        "role": "qa",
        "capabilities": ["qa.execute"],
        "resource_scopes": ["workspace/demo"],
        "budget": {"max_tokens": 2000, "max_cost_microunits": 200, "max_steps": 3},
        "context_manifest_required": True,
    }
    bounded = delegation.authorize_delegation(parent, child)
    expanded = delegation.authorize_delegation(parent, {**child, "capabilities": ["production.approve"]})
    orchestration = delegation.orchestrate({
        "workers": [child, {**child, "role": "independent-certifier"}],
        "max_workers": 2,
        "swarm_mode": False,
        "independent_certifier_separate": True,
    })
    assert bounded["decision"] == "ALLOW"
    assert expanded["decision"] == "DENY"
    assert orchestration["status"] == "READY_FOR_CONTROLLED_EXECUTION"

    result = {
        "schema": "vl.governed-orchestration-dryrun/1",
        "status": "READY_FOR_NONPRODUCTION_CONTROLLED_EXECUTION",
        "context_governance": {"allowed_count": context_payload["context_manifest"]["allowed_count"], "denied_count": context_payload["context_manifest"]["denied_count"]},
        "model_routing": {"selected_model_id": route["selected_model_id"], "decision_sha256": route["decision_sha256"]},
        "completion": {"status": completion_decision["status"], "decision_sha256": completion_decision["decision_sha256"]},
        "remediation": {"merge_prepare": merge_prepare["decision"], "merge_execute": merge_execute["decision"]},
        "connector": {"read": connector_read["decision"], "high_impact_without_approval": connector_write["decision"]},
        "execution_pool": {"decision": pool_decision["decision"], "attestation_promotable": attestation["promotable"]},
        "multi_agent": {"bounded_delegation": bounded["decision"], "authority_expansion": expanded["decision"], "status": orchestration["status"]},
        "live_model_invocation": False,
        "live_connector_invocation": False,
        "live_execution": False,
        "merge_executed": False,
        "production_approved": False,
        "production_deployed": False,
        "production_locked": True,
    }
    return result


if __name__ == "__main__":
    print(json.dumps(run_dryrun(), indent=2, sort_keys=True))
