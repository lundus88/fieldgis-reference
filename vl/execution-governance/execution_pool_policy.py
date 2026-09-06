#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def authorize_execution(pool: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    required = ('pool_id','profile_version','image_digest','network_policy','cpu_limit','memory_mb_limit')
    if any(not pool.get(k) for k in required):
        return _decision('DENY','INCOMPLETE_POOL_IDENTITY',pool,request)
    if pool.get('status') != 'certified':
        return _decision('DENY','UNCERTIFIED_EXECUTION_POOL',pool,request)
    if pool.get('ambient_production_credentials') is not False:
        return _decision('DENY','AMBIENT_PRODUCTION_CREDENTIALS_FORBIDDEN',pool,request)

    requested_capability = str(request.get('capability') or '')
    if requested_capability not in set(pool.get('allowed_capabilities') or []):
        return _decision('DENY','CAPABILITY_NOT_BOUND_TO_POOL',pool,request)

    if int(request.get('cpu') or 0) > int(pool['cpu_limit']):
        return _decision('DENY','CPU_LIMIT_EXCEEDED',pool,request)
    if int(request.get('memory_mb') or 0) > int(pool['memory_mb_limit']):
        return _decision('DENY','MEMORY_LIMIT_EXCEEDED',pool,request)

    required_network = str(request.get('network_policy') or '')
    if required_network and required_network != pool['network_policy']:
        return _decision('DENY','NETWORK_POLICY_MISMATCH',pool,request)

    return _decision('ALLOW','CERTIFIED_POOL_EXECUTION_ALLOWED',pool,request)


def attest_artifact(pool: dict[str, Any], artifact_sha256: str) -> dict[str, Any]:
    if pool.get('status') != 'certified' or pool.get('ambient_production_credentials') is not False:
        return {'promotable': False, 'reason': 'UNCERTIFIED_OR_UNSAFE_POOL', 'production_locked': True}
    evidence = {
        'pool_id': pool['pool_id'],
        'profile_version': pool['profile_version'],
        'image_digest': pool['image_digest'],
        'network_policy': pool['network_policy'],
        'artifact_sha256': artifact_sha256,
    }
    return {
        'schema':'vl.execution-pool-attestation/1',
        'promotable': True,
        'pool_id': pool['pool_id'],
        'profile_version': pool['profile_version'],
        'image_digest': pool['image_digest'],
        'network_policy': pool['network_policy'],
        'artifact_sha256': artifact_sha256,
        'attestation_sha256': canonical_sha256(evidence),
        'production_locked': True,
    }


def _decision(decision: str, reason: str, pool: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    core={'pool':pool,'request':request,'decision':decision,'reason':reason}
    return {
        'schema':'vl.execution-pool-decision/1',
        'decision':decision,
        'reason':reason,
        'pool_id':pool.get('pool_id'),
        'decision_sha256':canonical_sha256(core),
        'production_credentials_available':False,
        'production_locked':True,
    }
