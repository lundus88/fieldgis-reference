#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

ALLOWED_EVIDENCE_STATES = {'PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _require_sha(name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value.lower()):
        raise ValueError(f'{name} must be a 64-character sha256')


def validate_acceptance_inventory(inventory: dict[str, Any]) -> None:
    if inventory.get('schema') != 'vl.acceptance-inventory/1':
        raise ValueError('unsupported acceptance inventory schema')
    for key in ('app_spec_sha256', 'source_sha256'):
        _require_sha(key, str(inventory.get(key) or ''))
    items = inventory.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('acceptance inventory requires non-empty items')
    seen = set()
    for item in items:
        rid = str(item.get('requirement_id') or '').strip()
        if not rid or rid in seen:
            raise ValueError('requirement_id values must be unique and non-empty')
        seen.add(rid)
        if not str(item.get('description') or '').strip():
            raise ValueError(f'{rid} missing description')
        if item.get('required') is not True:
            raise ValueError(f'{rid} must be required in Phase 3 inventory')
        if not isinstance(item.get('accepted_evidence_types'), list) or not item['accepted_evidence_types']:
            raise ValueError(f'{rid} requires accepted_evidence_types')


def validate_evidence_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get('schema') != 'vl.acceptance-evidence/1':
        raise ValueError('unsupported evidence manifest schema')
    for key in ('app_spec_sha256', 'source_sha256', 'artifact_sha256'):
        _require_sha(key, str(manifest.get(key) or ''))
    evidence = manifest.get('evidence')
    if not isinstance(evidence, list):
        raise ValueError('evidence must be a list')
    for entry in evidence:
        if entry.get('state') not in ALLOWED_EVIDENCE_STATES:
            raise ValueError('invalid evidence state')
        if not str(entry.get('requirement_id') or '').strip():
            raise ValueError('evidence requirement_id required')
        if not str(entry.get('evidence_type') or '').strip():
            raise ValueError('evidence_type required')
        if not str(entry.get('evidence_digest') or '').strip():
            raise ValueError('evidence_digest required')


def validate_completion(inventory: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    validate_acceptance_inventory(inventory)
    validate_evidence_manifest(manifest)

    if manifest['app_spec_sha256'].lower() != inventory['app_spec_sha256'].lower():
        return _decision('FAIL', 'APP_SPEC_BINDING_MISMATCH', inventory, manifest, [])
    if manifest['source_sha256'].lower() != inventory['source_sha256'].lower():
        return _decision('FAIL', 'SOURCE_BINDING_MISMATCH', inventory, manifest, [])

    by_requirement: dict[str, list[dict[str, Any]]] = {}
    for entry in manifest['evidence']:
        by_requirement.setdefault(entry['requirement_id'], []).append(entry)

    results = []
    any_fail = False
    any_hold = False
    for item in inventory['items']:
        rid = item['requirement_id']
        allowed_types = set(item['accepted_evidence_types'])
        candidates = [e for e in by_requirement.get(rid, []) if e['evidence_type'] in allowed_types]
        states = {e['state'] for e in candidates}
        if 'FAIL' in states:
            state = 'FAIL'; reason = 'REQUIREMENT_EVIDENCE_FAILED'; any_fail = True
        elif 'PASS' in states:
            state = 'PASS'; reason = 'REQUIREMENT_EVIDENCE_SATISFIED'
        else:
            state = 'HOLD'; reason = 'REQUIRED_EVIDENCE_MISSING_OR_BLOCKED'; any_hold = True
        results.append({'requirement_id': rid, 'state': state, 'reason': reason, 'evidence_count': len(candidates)})

    overall = 'FAIL' if any_fail else ('HOLD' if any_hold else 'PASS')
    reason = 'REQUIREMENT_FAILED' if any_fail else ('INCOMPLETE_ACCEPTANCE_EVIDENCE' if any_hold else 'ALL_REQUIREMENTS_SATISFIED')
    return _decision(overall, reason, inventory, manifest, results)


def _decision(status: str, reason: str, inventory: dict[str, Any], manifest: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    decision_input = {
        'inventory_sha256': canonical_sha256(inventory),
        'manifest_sha256': canonical_sha256(manifest),
        'status': status,
        'reason': reason,
        'requirements': results,
    }
    return {
        'schema': 'vl.independent-completion-decision/1',
        'validator': 'vl-independent-validator-v1',
        'builder_self_report_trusted': False,
        'status': status,
        'reason': reason,
        'requirements': results,
        'inventory_sha256': decision_input['inventory_sha256'],
        'manifest_sha256': decision_input['manifest_sha256'],
        'decision_sha256': canonical_sha256(decision_input),
        'production_locked': True,
    }
