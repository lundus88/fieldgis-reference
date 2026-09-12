#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

ALLOWED_ENVIRONMENTS = {'development', 'staging'}


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def authorize_execution(pool: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    required = ('pool_id', 'profile_version', 'image_digest', 'network_policy', 'cpu_limit', 'memory_mb_limit')
    if any(not pool.get(key) for key in required):
        return _decision('DENY', 'INCOMPLETE_POOL_IDENTITY', pool, request)
    if pool.get('status') != 'certified':
        return _decision('DENY', 'UNCERTIFIED_EXECUTION_POOL', pool, request)
    if pool.get('ambient_production_credentials') is not False:
        return _decision('DENY', 'AMBIENT_PRODUCTION_CREDENTIALS_FORBIDDEN', pool, request)

    environment = str(request.get('target_environment') or '')
    if environment not in ALLOWED_ENVIRONMENTS:
        return _decision('DENY', 'NONPRODUCTION_ENVIRONMENT_REQUIRED', pool, request)

    capability = str(request.get('capability') or '')
    if capability not in set(pool.get('allowed_capabilities') or []):
        return _decision('DENY', 'CAPABILITY_NOT_BOUND_TO_POOL', pool, request)

    cpu = request.get('cpu')
    memory_mb = request.get('memory_mb')
    if not isinstance(cpu, int) or cpu < 1:
        return _decision('DENY', 'INVALID_CPU_REQUEST', pool, request)
    if not isinstance(memory_mb, int) or memory_mb < 1:
        return _decision('DENY', 'INVALID_MEMORY_REQUEST', pool, request)
    if cpu > int(pool['cpu_limit']):
        return _decision('DENY', 'CPU_LIMIT_EXCEEDED', pool, request)
    if memory_mb > int(pool['memory_mb_limit']):
        return _decision('DENY', 'MEMORY_LIMIT_EXCEEDED', pool, request)

    requested_network = str(request.get('network_policy') or '')
    if requested_network != pool['network_policy']:
        return _decision('DENY', 'NETWORK_POLICY_MISMATCH', pool, request)

    return _decision('ALLOW', 'CERTIFIED_NONPRODUCTION_POOL_ALLOWED', pool, request)


def attest_release_candidate(pool: dict[str, Any], artifact_sha256: str, target_environment: str) -> dict[str, Any]:
    if target_environment not in ALLOWED_ENVIRONMENTS:
        return {
            'schema': 'lom.execution-attestation/1',
            'release_candidate_eligible': False,
            'reason': 'NONPRODUCTION_ENVIRONMENT_REQUIRED',
            'production_locked': True,
        }
    if pool.get('status') != 'certified' or pool.get('ambient_production_credentials') is not False:
        return {
            'schema': 'lom.execution-attestation/1',
            'release_candidate_eligible': False,
            'reason': 'UNCERTIFIED_OR_UNSAFE_POOL',
            'production_locked': True,
        }
    if not isinstance(artifact_sha256, str) or len(artifact_sha256) != 64:
        return {
            'schema': 'lom.execution-attestation/1',
            'release_candidate_eligible': False,
            'reason': 'INVALID_ARTIFACT_SHA256',
            'production_locked': True,
        }

    evidence = {
        'pool_id': pool['pool_id'],
        'profile_version': pool['profile_version'],
        'image_digest': pool['image_digest'],
        'network_policy': pool['network_policy'],
        'target_environment': target_environment,
        'artifact_sha256': artifact_sha256,
    }
    return {
        'schema': 'lom.execution-attestation/1',
        'release_candidate_eligible': True,
        'pool_id': pool['pool_id'],
        'profile_version': pool['profile_version'],
        'image_digest': pool['image_digest'],
        'network_policy': pool['network_policy'],
        'target_environment': target_environment,
        'artifact_sha256': artifact_sha256,
        'attestation_sha256': canonical_sha256(evidence),
        'production_approval': False,
        'production_locked': True,
    }


def _decision(decision: str, reason: str, pool: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    core = {'pool': pool, 'request': request, 'decision': decision, 'reason': reason}
    return {
        'schema': 'lom.execution-pool-decision/1',
        'decision': decision,
        'reason': reason,
        'pool_id': pool.get('pool_id'),
        'decision_sha256': canonical_sha256(core),
        'production_credentials_available': False,
        'production_approval': False,
        'production_locked': True,
    }
