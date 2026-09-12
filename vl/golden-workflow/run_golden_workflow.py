#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {relpath}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    context = load_module('lom_context', 'vl/context-governance/pre_model_invocation.py')
    routing = load_module('lom_routing', 'vl/model-governance/route_model.py')
    execution = load_module('lom_execution', 'vl/execution-governance/execution_pool_policy.py')
    remediation = load_module('lom_remediation', 'vl/remediation-governance/remediation_policy.py')
    delegation = load_module('lom_delegation', 'vl/multi-agent-governance/delegation_policy.py')
    completion = load_module('lom_completion', 'vl/completion-governance/independent_validator.py')

    run_id = 'lom-golden-nonprod-001'
    app_spec = {
        'title': 'LOM Golden Workflow Fixture',
        'objective': 'Prove governed non-production workflow evidence without external side effects.',
        'target_environment': 'staging',
    }
    app_spec_sha = sha256_json(app_spec)

    resources = [{
        'resource_type': 'repo_path',
        'resource': 'src/example.py',
        'data_class': 'source_code',
        'content': 'print("fixture")',
    }]
    pre_model = context.build_pre_model_payload(
        policy_path=ROOT / 'vl/context-governance/default-context-policy.json',
        resources=resources,
        task={'kind': 'planning', 'instruction': app_spec['objective']},
    )
    context_policy_sha = sha256_json(json.loads((ROOT / 'vl/context-governance/default-context-policy.json').read_text()))

    registry = json.loads((ROOT / 'vl/model-governance/model-registry.json').read_text())
    model_decision = routing.route_model(registry, {
        'task_class': 'planning',
        'data_class': 'source_code',
        'input_tokens': 2000,
        'output_tokens': 1000,
        'cost_ceiling': 10.0,
        'autonomy_horizon': 1,
        'max_retention': 'none',
    })

    parent = {
        'capabilities': ['repo.read', 'branch.write', 'ci.inspect', 'pr.remediate'],
        'resource_scopes': ['repo:lundus88/fieldgis-reference', 'branch:lom-v1'],
        'budget': {
            'max_tokens': 100000,
            'max_cost_microunits': 1000000,
            'max_steps': 50,
            'max_time_seconds': 1800,
            'max_retries': 3,
        },
    }
    child = {
        'role': 'implementer',
        'capabilities': ['repo.read', 'branch.write'],
        'resource_scopes': ['repo:lundus88/fieldgis-reference'],
        'budget': {
            'max_tokens': 40000,
            'max_cost_microunits': 400000,
            'max_steps': 20,
            'max_time_seconds': 600,
            'max_retries': 1,
        },
        'context_manifest_required': True,
        'context_policy_sha256': context_policy_sha,
        'parent_run_id': run_id,
    }
    delegation_decision = delegation.authorize_delegation(parent, child)
    orchestration = delegation.orchestrate({
        'workers': [
            {'id': 'planner-1', 'role': 'planner'},
            {'id': 'builder-1', 'role': 'implementer'},
            {'id': 'qa-1', 'role': 'qa'},
            {'id': 'cert-1', 'role': 'independent-certifier'},
        ],
        'max_workers': 4,
        'swarm_mode': False,
    })

    pool = {
        'pool_id': 'lom-ci-linux-x64',
        'profile_version': '1.0.0',
        'image_digest': 'sha256:' + ('1' * 64),
        'network_policy': 'egress-restricted',
        'cpu_limit': 2,
        'memory_mb_limit': 4096,
        'allowed_capabilities': ['build.execute', 'test.execute'],
        'ambient_production_credentials': False,
        'status': 'certified',
    }
    execution_decision = execution.authorize_execution(pool, {
        'capability': 'build.execute',
        'cpu': 1,
        'memory_mb': 1024,
        'network_policy': 'egress-restricted',
        'target_environment': 'staging',
    })

    artifact = {'fixture': 'LOM Golden Workflow artifact', 'run_id': run_id}
    artifact_sha = sha256_json(artifact)
    attestation = execution.attest_release_candidate(pool, artifact_sha, 'staging')

    failure_evidence = sha256_json({'state': 'PASS', 'detail': 'No remediation required in golden run.'})
    remediation_decision = remediation.authorize({
        'capability': 'ci.inspect',
        'target_branch': 'lom-v1',
        'attempt': 1,
        'failure_evidence_sha256': failure_evidence,
    }, {
        'capabilities': ['ci.inspect'],
        'protected_branches': ['main'],
        'max_remediation_attempts': 2,
    })

    inventory = {
        'schema': 'vl.acceptance-inventory/1',
        'app_spec_sha256': app_spec_sha,
        'source_sha256': artifact_sha,
        'items': [
            {'requirement_id': 'REQ-CONTEXT', 'description': 'Context is governed', 'required': True, 'accepted_evidence_types': ['context']},
            {'requirement_id': 'REQ-ROUTING', 'description': 'Model routing is governed', 'required': True, 'accepted_evidence_types': ['routing']},
            {'requirement_id': 'REQ-EXECUTION', 'description': 'Execution is non-production and bounded', 'required': True, 'accepted_evidence_types': ['execution']},
            {'requirement_id': 'REQ-DELEGATION', 'description': 'Delegation is non-expanding', 'required': True, 'accepted_evidence_types': ['delegation']},
        ],
    }
    evidence_manifest = {
        'schema': 'vl.acceptance-evidence/1',
        'app_spec_sha256': app_spec_sha,
        'source_sha256': artifact_sha,
        'artifact_sha256': artifact_sha,
        'evidence': [
            {'requirement_id': 'REQ-CONTEXT', 'evidence_type': 'context', 'state': 'PASS', 'evidence_digest': pre_model['context_manifest']['policy_id']},
            {'requirement_id': 'REQ-ROUTING', 'evidence_type': 'routing', 'state': 'PASS', 'evidence_digest': model_decision['decision_sha256']},
            {'requirement_id': 'REQ-EXECUTION', 'evidence_type': 'execution', 'state': 'PASS', 'evidence_digest': execution_decision['decision_sha256']},
            {'requirement_id': 'REQ-DELEGATION', 'evidence_type': 'delegation', 'state': 'PASS', 'evidence_digest': delegation_decision['decision_sha256']},
        ],
    }
    completion_decision = completion.validate_completion(inventory, evidence_manifest)

    checks = {
        'context': pre_model['production_locked'] is True and pre_model['raw_candidates_forwarded'] is False,
        'routing': model_decision['production_locked'] is True,
        'delegation': delegation_decision['decision'] == 'ALLOW' and delegation_decision['authority_expanded'] is False,
        'orchestration': orchestration['status'] == 'READY_FOR_CONTROLLED_EXECUTION' and orchestration['production_locked'] is True,
        'execution': execution_decision['decision'] == 'ALLOW' and execution_decision['production_locked'] is True,
        'attestation': attestation['release_candidate_eligible'] is True and attestation['production_approval'] is False,
        'remediation': remediation_decision['decision'] == 'ALLOW' and remediation_decision['production_locked'] is True,
        'completion': completion_decision['status'] == 'PASS' and completion_decision['builder_self_report_trusted'] is False,
    }

    overall = 'PASS' if all(checks.values()) else 'FAIL'
    bundle = {
        'schema': 'lom.golden-workflow-evidence/1',
        'run_id': run_id,
        'environment': 'staging-fixture',
        'external_side_effects': False,
        'live_provider_calls': False,
        'live_connector_calls': False,
        'production_credentials_used': False,
        'production_approval': False,
        'production_deployment': False,
        'status': overall,
        'checks': checks,
        'app_spec_sha256': app_spec_sha,
        'context_policy_sha256': context_policy_sha,
        'model_routing_decision_sha256': model_decision['decision_sha256'],
        'delegation_decision_sha256': delegation_decision['decision_sha256'],
        'execution_decision_sha256': execution_decision['decision_sha256'],
        'artifact_sha256': artifact_sha,
        'completion_decision_sha256': completion_decision['decision_sha256'],
    }
    bundle['bundle_sha256'] = sha256_json(bundle)

    output = Path(__file__).with_name('golden-workflow-evidence.json')
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + '\n')
    print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0 if overall == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
