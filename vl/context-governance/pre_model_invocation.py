from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from build_context_manifest import build_context


class ContextGovernanceBlocked(RuntimeError):
    pass


def build_pre_model_payload(*, policy_path: str | Path, resources: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
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
