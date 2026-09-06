#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

ALLOWED_ROLES = {'planner','implementer','qa','security-reviewer','release-preparation','independent-certifier'}
FORBIDDEN_CAPABILITIES = {'merge.execute','production.approve','production.deploy','branch.force_push'}


def canonical_sha256(value: Any) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def authorize_delegation(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    role=str(child.get('role') or '')
    if role not in ALLOWED_ROLES:
        return _decision('DENY','UNKNOWN_AGENT_ROLE',parent,child)

    parent_caps=set(parent.get('capabilities') or [])
    child_caps=set(child.get('capabilities') or [])
    if child_caps & FORBIDDEN_CAPABILITIES:
        return _decision('DENY','FORBIDDEN_CAPABILITY_REQUESTED',parent,child)
    if not child_caps.issubset(parent_caps):
        return _decision('DENY','CAPABILITY_EXPANSION_BLOCKED',parent,child)

    parent_scope=set(parent.get('resource_scopes') or [])
    child_scope=set(child.get('resource_scopes') or [])
    if not child_scope.issubset(parent_scope):
        return _decision('DENY','RESOURCE_SCOPE_EXPANSION_BLOCKED',parent,child)

    parent_budget=parent.get('budget') or {}
    child_budget=child.get('budget') or {}
    for key in ('max_tokens','max_cost_microunits','max_steps'):
        if int(child_budget.get(key) or 0) > int(parent_budget.get(key) or 0):
            return _decision('DENY','BUDGET_EXPANSION_BLOCKED',parent,child)

    if child.get('context_manifest_required') is not True:
        return _decision('DENY','GOVERNED_CONTEXT_REQUIRED',parent,child)

    return _decision('ALLOW','BOUNDED_DELEGATION_ALLOWED',parent,child)


def orchestrate(plan: dict[str, Any]) -> dict[str, Any]:
    workers=plan.get('workers') or []
    if len(workers) > int(plan.get('max_workers') or 0):
        return {'status':'BLOCKED','reason':'WORKER_LIMIT_EXCEEDED','production_locked':True}
    if plan.get('swarm_mode') is True:
        return {'status':'BLOCKED','reason':'SWARM_MODE_FORBIDDEN_BY_DEFAULT','production_locked':True}
    if plan.get('independent_certifier_separate') is not True:
        return {'status':'BLOCKED','reason':'INDEPENDENT_CERTIFIER_REQUIRED','production_locked':True}
    return {
        'schema':'vl.multi-agent-orchestration/1',
        'status':'READY_FOR_CONTROLLED_EXECUTION',
        'worker_count':len(workers),
        'production_approval':'HUMAN_ONLY',
        'production_locked':True,
        'plan_sha256':canonical_sha256(plan),
    }


def _decision(decision: str, reason: str, parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    core={'parent':parent,'child':child,'decision':decision,'reason':reason}
    return {
        'schema':'vl.delegation-policy-decision/1',
        'decision':decision,
        'reason':reason,
        'child_role':child.get('role'),
        'decision_sha256':canonical_sha256(core),
        'authority_expanded':False,
        'production_approval':'HUMAN_ONLY',
        'production_locked':True,
    }
