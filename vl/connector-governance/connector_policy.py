#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def authorize_connector_call(connector: dict[str, Any], request: dict[str, Any], grant: dict[str, Any]) -> dict[str, Any]:
    cid = str(connector.get('id') or '')
    version = str(connector.get('version') or '')
    if not cid or not version or connector.get('status') != 'certified':
        return _decision('DENY','UNCERTIFIED_CONNECTOR',connector,request,grant)
    if connector.get('ambient_credentials') is not False:
        return _decision('DENY','AMBIENT_CREDENTIALS_FORBIDDEN',connector,request,grant)

    capability = f'connector.invoke:{cid}'
    if capability not in set(grant.get('capabilities') or []):
        return _decision('DENY','CONNECTOR_CAPABILITY_NOT_GRANTED',connector,request,grant)

    operation = str(request.get('operation') or '')
    resource = str(request.get('resource') or '')
    if operation not in set(connector.get('allowed_operations') or []):
        return _decision('DENY','OPERATION_OUT_OF_SCOPE',connector,request,grant)
    scopes = [str(x) for x in connector.get('resource_scopes') or []]
    if not any(resource == s or resource.startswith(s.rstrip('/') + '/') for s in scopes):
        return _decision('DENY','RESOURCE_OUT_OF_SCOPE',connector,request,grant)

    high_impact = operation in set(connector.get('high_impact_operations') or [])
    paid = operation in set(connector.get('paid_operations') or [])
    if (high_impact or paid) and request.get('human_approval') is not True:
        return _decision('DENY','HUMAN_APPROVAL_REQUIRED',connector,request,grant)

    return _decision('ALLOW','CERTIFIED_CONNECTOR_CALL_ALLOWED',connector,request,grant)


def _decision(decision: str, reason: str, connector: dict[str, Any], request: dict[str, Any], grant: dict[str, Any]) -> dict[str, Any]:
    core = {'connector': {'id': connector.get('id'), 'version': connector.get('version')}, 'request': request, 'grant': grant, 'decision': decision, 'reason': reason}
    return {
        'schema': 'vl.connector-decision/1',
        'decision': decision,
        'reason': reason,
        'connector_id': connector.get('id'),
        'connector_version': connector.get('version'),
        'request_sha256': canonical_sha256(request),
        'grant_sha256': canonical_sha256(grant),
        'decision_sha256': canonical_sha256(core),
        'secret_material_exposed': False,
        'ambient_credentials_used': False,
        'production_locked': True,
    }
