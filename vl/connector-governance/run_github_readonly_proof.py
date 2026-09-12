#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from github_readonly_connector import authorize, canonical_sha256, invoke_public_repo_metadata


def main() -> int:
    resource = 'github:repo:lundus88/fieldgis-reference'
    grant = {
        'capabilities': ['connector.read:github-public-readonly-v1'],
        'resource_scopes': [resource],
        'production_approval': False,
    }

    allowed_request = {
        'operation': 'repo.metadata.read',
        'resource': resource,
    }
    allowed = authorize(allowed_request, grant)

    scope_escape = authorize({
        'operation': 'repo.metadata.read',
        'resource': 'github:repo:octocat/Hello-World',
    }, grant)

    non_read = authorize({
        'operation': 'repo.metadata.write',
        'resource': resource,
    }, grant)

    runtime = invoke_public_repo_metadata('lundus88', 'fieldgis-reference') if allowed['decision'] == 'ALLOW' else None

    checks = {
        'allowed_request': allowed['decision'] == 'ALLOW',
        'scope_escape_blocked': scope_escape['decision'] == 'DENY',
        'non_read_blocked': non_read['decision'] == 'DENY',
        'runtime_http_200': bool(runtime and runtime['http_status'] == 200),
        'correct_repository': bool(runtime and runtime['result']['full_name'] == 'lundus88/fieldgis-reference'),
        'no_credentials': bool(runtime and runtime['credentials_used'] is False),
        'no_write_authority': bool(runtime and runtime['write_authority'] is False),
        'production_locked': bool(runtime and runtime['production_locked'] is True),
    }

    evidence = {
        'schema': 'lom.live-connector-runtime-evidence/1',
        'connector_id': 'github-public-readonly-v1',
        'connector_version': '1.0.0',
        'environment': 'non-production-public-runtime',
        'operation': 'repo.metadata.read',
        'resource': resource,
        'request_sha256': allowed['request_sha256'],
        'grant_sha256': allowed['grant_sha256'],
        'decision_sha256': allowed['decision_sha256'],
        'runtime_result_sha256': canonical_sha256(runtime),
        'credentials_used': False,
        'write_authority': False,
        'production_approval': False,
        'production_deployment': False,
        'checks': checks,
        'status': 'PASS' if all(checks.values()) else 'FAIL',
    }
    evidence['evidence_sha256'] = canonical_sha256(evidence)

    out = Path(__file__).with_name('github-readonly-runtime-evidence.json')
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
