#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

ALLOWED_ROLES = {
    'planner',
    'implementer',
    'qa',
    'security-reviewer',
    'release-preparation',
    'independent-certifier',
}
FORBIDDEN_CAPABILITIES = {
    'merge.execute',
    'production.approve',
    'production.deploy',
    'branch.force_push',
}
BUDGET_KEYS = ('max_tokens', 'max_cost_microunits', 'max_steps', 'max_time_seconds', 'max_retries')


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or '')
    return len(text) == 64 and all(ch in '0123456789abcdefABCDEF' for ch in text)


def authorize_delegation(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    role = str(child.get('role') or '')
    if role not in ALLOWED_ROLES:
        return _decision('DENY', 'UNKNOWN_AGENT_ROLE', parent, child)

    parent_caps = set(parent.get('capabilities') or [])
    child_caps = set(child.get('capabilities') or [])
    if child_caps & FORBIDDEN_CAPABILITIES:
        return _decision('DENY', 'FORBIDDEN_CAPABILITY_REQUESTED', parent, child)
    if not child_caps.issubset(parent_caps):
        return _decision('DENY', 'CAPABILITY_EXPANSION_BLOCKED', parent, child)

    parent_scope = set(parent.get('resource_scopes') or [])
    child_scope = set(child.get('resource_scopes') or [])
    if not child_scope or not child_scope.issubset(parent_scope):
        return _decision('DENY', 'RESOURCE_SCOPE_EXPANSION_BLOCKED', parent, child)

    parent_budget = parent.get('budget') or {}
    child_budget = child.get('budget') or {}
    for key in BUDGET_KEYS:
        p = parent_budget.get(key)
        c = child_budget.get(key)
        if not isinstance(p, int) or p < 0 or not isinstance(c, int) or c < 0:
            return _decision('DENY', 'INVALID_BUDGET', parent, child)
        if c > p:
            return _decision('DENY', 'BUDGET_EXPANSION_BLOCKED', parent, child)

    if child.get('context_manifest_required') is not True:
        return _decision('DENY', 'GOVERNED_CONTEXT_REQUIRED', parent, child)
    if not _valid_sha256(child.get('context_policy_sha256')):
        return _decision('DENY', 'CONTEXT_POLICY_DIGEST_REQUIRED', parent, child)
    if not str(child.get('parent_run_id') or '').strip():
        return _decision('DENY', 'PARENT_RUN_ID_REQUIRED', parent, child)

    return _decision('ALLOW', 'BOUNDED_DELEGATION_ALLOWED', parent, child)


def orchestrate(plan: dict[str, Any]) -> dict[str, Any]:
    workers = plan.get('workers') or []
    if not isinstance(workers, list) or not workers:
        return _orchestration_block('WORKERS_REQUIRED')
    max_workers = plan.get('max_workers')
    if not isinstance(max_workers, int) or max_workers < 1 or len(workers) > max_workers:
        return _orchestration_block('WORKER_LIMIT_EXCEEDED')
    if plan.get('swarm_mode') is True:
        return _orchestration_block('SWARM_MODE_FORBIDDEN_BY_DEFAULT')

    identities = [str(w.get('id') or '') for w in workers if isinstance(w, dict)]
    roles = [str(w.get('role') or '') for w in workers if isinstance(w, dict)]
    if len(identities) != len(workers) or any(not x for x in identities) or len(set(identities)) != len(identities):
        return _orchestration_block('UNIQUE_WORKER_IDENTITIES_REQUIRED')
    if any(role not in ALLOWED_ROLES for role in roles):
        return _orchestration_block('UNKNOWN_AGENT_ROLE')
    if 'implementer' not in roles or 'independent-certifier' not in roles:
        return _orchestration_block('IMPLEMENTER_AND_CERTIFIER_REQUIRED')

    implementers = {w['id'] for w in workers if w['role'] == 'implementer'}
    certifiers = {w['id'] for w in workers if w['role'] == 'independent-certifier'}
    if implementers & certifiers:
        return _orchestration_block('CERTIFIER_MUST_BE_SEPARATE')

    return {
        'schema': 'lom.multi-agent-orchestration/1',
        'status': 'READY_FOR_CONTROLLED_EXECUTION',
        'worker_count': len(workers),
        'worker_ids': identities,
        'production_approval': 'HUMAN_ONLY',
        'production_locked': True,
        'plan_sha256': canonical_sha256(plan),
    }


def _orchestration_block(reason: str) -> dict[str, Any]:
    return {
        'schema': 'lom.multi-agent-orchestration/1',
        'status': 'BLOCKED',
        'reason': reason,
        'production_approval': 'HUMAN_ONLY',
        'production_locked': True,
    }


def _decision(decision: str, reason: str, parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    core = {'parent': parent, 'child': child, 'decision': decision, 'reason': reason}
    return {
        'schema': 'lom.delegation-policy-decision/1',
        'decision': decision,
        'reason': reason,
        'child_role': child.get('role'),
        'decision_sha256': canonical_sha256(core),
        'authority_expanded': False,
        'production_approval': 'HUMAN_ONLY',
        'production_locked': True,
    }
