#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def validate(registry: dict) -> None:
    if registry.get('schema') != 'lom.connector-registry/1':
        raise ValueError('unsupported connector registry schema')
    if registry.get('default_decision') != 'deny':
        raise ValueError('connector registry must be deny-by-default')
    if registry.get('production_locked') is not True:
        raise ValueError('production must remain locked')
    if registry.get('write_authority') is not False:
        raise ValueError('write authority must remain false')
    if registry.get('paid_action_authority') is not False:
        raise ValueError('paid action authority must remain false')
    if registry.get('ambient_credentials_allowed') is not False:
        raise ValueError('ambient credentials must remain forbidden')

    connectors = registry.get('connectors')
    if not isinstance(connectors, list) or not connectors:
        raise ValueError('at least one connector fixture is required')

    seen = set()
    for connector in connectors:
        cid = str(connector.get('id') or '')
        version = str(connector.get('version') or '')
        if not cid or not version or cid in seen:
            raise ValueError('connector id/version must be non-empty and unique')
        seen.add(cid)
        if connector.get('status') != 'certified-fixture':
            raise ValueError(f'connector {cid} must be certified-fixture')
        if connector.get('mode') != 'read-only':
            raise ValueError(f'connector {cid} must be read-only')
        if connector.get('allowed_operations') != ['read']:
            raise ValueError(f'connector {cid} may allow read only')
        scopes = connector.get('resource_scopes')
        if not isinstance(scopes, list) or not scopes or any(not str(x).strip() for x in scopes):
            raise ValueError(f'connector {cid} requires explicit resource scopes')
        if connector.get('external_runtime') is not False:
            raise ValueError(f'connector {cid} must not enable external runtime')
        if connector.get('credentials_required') is not False:
            raise ValueError(f'connector {cid} must not require credentials')


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: validate_connector_registry.py <registry.json>', file=sys.stderr)
        return 2
    try:
        registry = json.loads(Path(sys.argv[1]).read_text())
        validate(registry)
        print('LOM CONNECTOR REGISTRY: PASS')
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
