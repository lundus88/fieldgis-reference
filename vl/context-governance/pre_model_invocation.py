from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from build_context_manifest import build_context


class ContextGovernanceBlocked(RuntimeError):
    pass


def build_pre_model_payload(*, policy_path: str | Path, resources: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
    """Build the only payload shape permitted to cross a future model boundary.

    Candidate resources are evaluated before payload construction. Denied resource
    content is omitted entirely. Provenance records only decisions and SHA-256
    digests, never denied secret values.
    """
    policy = json.loads(Path(policy_path).read_text())
    result = build_context(policy, resources)

    if resources and not result['context']:
        raise ContextGovernanceBlocked('CONTEXT_GOVERNANCE_BLOCKED: no candidate resources are allowed')

    return {
        'schema': 'vl.pre-model-invocation/1',
        'task': task,
        'context': result['context'],
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
