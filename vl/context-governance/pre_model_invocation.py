from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from build_context_manifest import build_context_manifest
from validate_context_policy import load_policy


class ContextGovernanceBlocked(RuntimeError):
    pass


def build_pre_model_payload(*, policy_path: str | Path, resources: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
    """Build the only payload shape permitted to cross a future model boundary.

    Raw candidate resources are never forwarded directly. The context manifest is
    built first, denied resources are excluded, and the resulting payload carries
    only approved context plus non-secret provenance metadata.
    """
    policy = load_policy(policy_path)
    result = build_context_manifest(policy, resources)

    allowed_context: list[dict[str, Any]] = []
    allowed_ids = {entry['resource_id'] for entry in result['manifest']['resources'] if entry['decision'] == 'allow'}
    for resource in resources:
        rid = str(resource.get('resource_id', ''))
        if rid in allowed_ids:
            allowed_context.append({
                'resource_id': rid,
                'resource_type': resource.get('resource_type'),
                'path': resource.get('path'),
                'content': resource.get('content'),
            })

    if resources and not allowed_context:
        raise ContextGovernanceBlocked('CONTEXT_GOVERNANCE_BLOCKED: no candidate resources are allowed')

    return {
        'schema': 'vl.pre-model-invocation/1',
        'task': task,
        'context': allowed_context,
        'context_manifest': result['manifest'],
        'production_locked': True,
        'raw_candidates_forwarded': False,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('policy')
    parser.add_argument('request_json')
    args = parser.parse_args()

    request = json.loads(Path(args.request_json).read_text())
    payload = build_pre_model_payload(
        policy_path=args.policy,
        resources=request.get('resources', []),
        task=request.get('task', {}),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
