#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

ALLOWED_CAPABILITIES = {
    'pr.inspect',
    'pr.remediate',
    'ci.inspect',
    'ci.repair',
    'merge.prepare',
}
FORBIDDEN_CAPABILITIES = {
    'merge.execute',
    'production.approve',
    'production.deploy',
    'branch.force_push',
}


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def authorize(action: dict[str, Any], grant: dict[str, Any]) -> dict[str, Any]:
    capability = str(action.get('capability') or '')
    if capability in FORBIDDEN_CAPABILITIES:
        return _decision('DENY', 'FORBIDDEN_CAPABILITY', action, grant)
    if capability not in ALLOWED_CAPABILITIES:
        return _decision('DENY', 'UNKNOWN_CAPABILITY', action, grant)

    granted = set(grant.get('capabilities') or [])
    if capability not in granted:
        return _decision('DENY', 'CAPABILITY_NOT_GRANTED', action, grant)

    target_branch = str(action.get('target_branch') or '')
    protected = set(grant.get('protected_branches') or ['main'])
    if capability in {'pr.remediate', 'ci.repair'} and target_branch in protected:
        return _decision('DENY', 'PROTECTED_BRANCH_MUTATION_BLOCKED', action, grant)

    if capability == 'merge.prepare':
        return _decision('ALLOW', 'MERGE_READY_RECOMMENDATION_ONLY', action, grant, authority='recommendation_only')

    return _decision('ALLOW', 'CAPABILITY_SCOPED_ACTION_ALLOWED', action, grant, authority='branch_scoped')


def _decision(decision: str, reason: str, action: dict[str, Any], grant: dict[str, Any], authority: str = 'none') -> dict[str, Any]:
    evidence_input = {'action': action, 'grant': grant, 'decision': decision, 'reason': reason, 'authority': authority}
    return {
        'schema': 'vl.remediation-policy-decision/1',
        'decision': decision,
        'reason': reason,
        'capability': action.get('capability'),
        'authority': authority,
        'action_sha256': canonical_sha256(action),
        'grant_sha256': canonical_sha256(grant),
        'decision_sha256': canonical_sha256(evidence_input),
        'merge_executed': False,
        'production_approved': False,
        'production_locked': True,
    }
