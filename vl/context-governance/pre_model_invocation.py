from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from build_context_manifest import build_context
from context_compaction import compact_allowed_context, validate_compaction_manifest


class ContextGovernanceBlocked(RuntimeError):
    pass


def build_pre_model_payload(
    *,
    policy_path: str | Path,
    resources: list[dict[str, Any]],
    task: dict[str, Any],
    max_context_chars: int | None = None,
    compaction_chunk_chars: int = 1200,
) -> dict[str, Any]:
    policy = json.loads(Path(policy_path).read_text())
    result = build_context(policy, resources)

    if resources and not result['context']:
        raise ContextGovernanceBlocked(
            'CONTEXT_GOVERNANCE_BLOCKED: no candidate resources are allowed'
        )

    context = result['context']
    compaction_manifest = None
    context_compacted = False

    if max_context_chars is not None and context:
        compacted = compact_allowed_context(
            context,
            task=task,
            max_context_chars=max_context_chars,
            chunk_chars=compaction_chunk_chars,
        )
        if compacted.get('status') != 'READY':
            raise ContextGovernanceBlocked(
                f"CONTEXT_COMPACTION_BLOCKED: {compacted.get('reason', 'UNKNOWN')}"
            )
        validation = validate_compaction_manifest(compacted['manifest'])
        if validation.get('status') != 'READY':
            raise ContextGovernanceBlocked(
                f"CONTEXT_COMPACTION_BLOCKED: {validation.get('reason', 'INVALID_MANIFEST')}"
            )
        context = compacted['context']
        compaction_manifest = compacted['manifest']
        context_compacted = bool(compaction_manifest.get('compacted'))

    return {
        'schema': 'vl.pre-model-invocation/1',
        'task': task,
        'context': context,
        'context_manifest': result['manifest'],
        'context_compacted': context_compacted,
        'context_compaction_manifest': compaction_manifest,
        'production_locked': True,
        'raw_candidates_forwarded': False,
        'source_truth_preserved': True,
        'abstractive_context_summary_generated': False,
    }
