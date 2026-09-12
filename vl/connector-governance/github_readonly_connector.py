#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import urllib.request
from typing import Any

CONNECTOR_ID = 'github-public-readonly-v1'
CONNECTOR_VERSION = '1.0.0'
ALLOWED_OPERATION = 'repo.metadata.read'
ALLOWED_RESOURCE_PREFIX = 'github:repo:'


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def authorize(request: dict[str, Any], grant: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get('operation') or '')
    resource = str(request.get('resource') or '')
    grant_caps = set(grant.get('capabilities') or [])
    grant_scopes = set(grant.get('resource_scopes') or [])

    if operation != ALLOWED_OPERATION:
        return _decision('DENY', 'NON_READ_OPERATION_BLOCKED', request, grant)
    if f'connector.read:{CONNECTOR_ID}' not in grant_caps:
        return _decision('DENY', 'CAPABILITY_NOT_GRANTED', request, grant)
    if not resource.startswith(ALLOWED_RESOURCE_PREFIX):
        return _decision('DENY', 'INVALID_RESOURCE', request, grant)
    if resource not in grant_scopes:
        return _decision('DENY', 'RESOURCE_SCOPE_ESCAPE_BLOCKED', request, grant)

    return _decision('ALLOW', 'READ_ONLY_REQUEST_ALLOWED', request, grant)


def invoke_public_repo_metadata(owner: str, repo: str) -> dict[str, Any]:
    url = f'https://api.github.com/repos/{owner}/{repo}'
    req = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'lom-readonly-proof/1.0',
        },
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = json.loads(response.read().decode('utf-8'))
    return {
        'connector_id': CONNECTOR_ID,
        'connector_version': CONNECTOR_VERSION,
        'operation': ALLOWED_OPERATION,
        'resource': f'github:repo:{owner}/{repo}',
        'http_status': 200,
        'result': {
            'full_name': body.get('full_name'),
            'visibility': body.get('visibility'),
            'default_branch': body.get('default_branch'),
            'archived': body.get('archived'),
        },
        'credentials_used': False,
        'write_authority': False,
        'production_locked': True,
    }


def _decision(decision: str, reason: str, request: dict[str, Any], grant: dict[str, Any]) -> dict[str, Any]:
    evidence = {
        'connector_id': CONNECTOR_ID,
        'connector_version': CONNECTOR_VERSION,
        'request_sha256': canonical_sha256(request),
        'grant_sha256': canonical_sha256(grant),
        'decision': decision,
        'reason': reason,
    }
    return {
        'schema': 'lom.connector-decision/1',
        **evidence,
        'decision_sha256': canonical_sha256(evidence),
        'write_authority': False,
        'credentials_exposed': False,
        'production_locked': True,
    }
