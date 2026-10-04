#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable

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
        if item.get('required') is not True:
            raise ValueError(f'{rid} must be required')
        if not isinstance(item.get('accepted_evidence_types'), list) or not item['accepted_evidence_types']:
            raise ValueError(f'{rid} requires accepted_evidence_types')


def validate_evidence_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get('schema') != 'vl.acceptance-evidence/1':
        raise ValueError('unsupported evidence manifest schema')
    for key in ('app_spec_sha256', 'source_sha256', 'artifact_sha256'):
        _require_sha(key, str(manifest.get(key) or ''))
    if not isinstance(manifest.get('evidence'), list):
        raise ValueError('evidence must be a list')
    for entry in manifest['evidence']:
        if entry.get('state') not in ALLOWED_EVIDENCE_STATES:
            raise ValueError('invalid evidence state')
        for key in ('requirement_id', 'evidence_type', 'evidence_digest'):
            if not str(entry.get(key) or '').strip():
                raise ValueError(f'{key} required')


def validate_completion(inventory: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    validate_acceptance_inventory(inventory)
    validate_evidence_manifest(manifest)
    if manifest['app_spec_sha256'].lower() != inventory['app_spec_sha256'].lower():
        return _decision('FAIL', 'APP_SPEC_BINDING_MISMATCH', inventory, manifest, [])
    if manifest['source_sha256'].lower() != inventory['source_sha256'].lower():
        return _decision('FAIL', 'SOURCE_BINDING_MISMATCH', inventory, manifest, [])
    by_requirement = {}
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
            state, reason, any_fail = 'FAIL', 'REQUIREMENT_EVIDENCE_FAILED', True
        elif 'PASS' in states:
            state, reason = 'PASS', 'REQUIREMENT_EVIDENCE_SATISFIED'
        else:
            state, reason, any_hold = 'HOLD', 'REQUIRED_EVIDENCE_MISSING_OR_BLOCKED', True
        results.append({'requirement_id': rid, 'state': state, 'reason': reason, 'evidence_count': len(candidates)})
    overall = 'FAIL' if any_fail else ('HOLD' if any_hold else 'PASS')
    reason = 'REQUIREMENT_FAILED' if any_fail else ('INCOMPLETE_ACCEPTANCE_EVIDENCE' if any_hold else 'ALL_REQUIREMENTS_SATISFIED')
    return _decision(overall, reason, inventory, manifest, results)


def _decision(status, reason, inventory, manifest, results):
    decision_input = {'inventory_sha256': canonical_sha256(inventory), 'manifest_sha256': canonical_sha256(manifest), 'status': status, 'reason': reason, 'requirements': results}
    return {
        'schema': 'vl.independent-completion-decision/1',
        'validator': 'lom-independent-validator-v1',
        'builder_self_report_trusted': False,
        'status': status,
        'reason': reason,
        'requirements': results,
        'inventory_sha256': decision_input['inventory_sha256'],
        'manifest_sha256': decision_input['manifest_sha256'],
        'decision_sha256': canonical_sha256(decision_input),
        'production_locked': True,
    }


CONSENSUS_SCHEMA = 'vl.verifier-consensus-decision/1'
ALLOWED_VERIFIER_STATES = {'PASS', 'FAIL', 'HOLD'}


@dataclass(frozen=True)
class VerifierReport:
    validator_id: str
    executor_id: str
    decision_sha256: str
    status: str
    evidence_ref: str
    evidence_fresh: bool
    confidence: float
    method_id: str


@dataclass(frozen=True)
class ConsensusPolicy:
    minimum_validators: int = 2
    minimum_methods: int = 2
    maximum_confidence_spread: float = 0.20
    require_unique_evidence_refs: bool = True


def _addressable_ref(value: str) -> bool:
    v = str(value or '').strip()
    return bool(v) and ('://' in v or v.startswith('urn:') or v.startswith('sha256:'))


def _consensus_decision(
    status: str,
    reason: str,
    base_decision: dict[str, Any],
    reports: Iterable[VerifierReport],
    *,
    policy: ConsensusPolicy,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    rows = list(reports)
    confidences = [float(r.confidence) for r in rows] if rows else []
    body = {
        'schema': CONSENSUS_SCHEMA,
        'status': status,
        'reason': reason,
        'base_decision_sha256': base_decision.get('decision_sha256'),
        'base_status': base_decision.get('status'),
        'validator_count': len(rows),
        'method_count': len({r.method_id for r in rows}),
        'evidence_ref_count': len({r.evidence_ref for r in rows}),
        'confidence_min': min(confidences) if confidences else None,
        'confidence_max': max(confidences) if confidences else None,
        'confidence_spread': (max(confidences) - min(confidences)) if confidences else None,
        'errors': sorted(errors or []),
        'validator_ids': sorted(r.validator_id for r in rows),
        'method_ids': sorted({r.method_id for r in rows}),
        'execution_authority': 'NONE',
        'execution_performed': False,
        'production_locked': True,
        'production_authority': 'HUMAN_ONLY',
        'protected_main_merge': 'HUMAN_ONLY',
        'self_approval': 'FORBIDDEN',
        'authority_widening': 'DISABLED',
        'builder_self_report_trusted': False,
        'high_assurance_verified': status == 'PASS',
        'policy': {
            'minimum_validators': policy.minimum_validators,
            'minimum_methods': policy.minimum_methods,
            'maximum_confidence_spread': policy.maximum_confidence_spread,
            'require_unique_evidence_refs': policy.require_unique_evidence_refs,
            'unanimous_pass_required': True,
        },
    }
    return {**body, 'consensus_sha256': canonical_sha256(body)}


def validate_completion_consensus(
    base_decision: dict[str, Any],
    reports: Iterable[VerifierReport],
    *,
    policy: ConsensusPolicy = ConsensusPolicy(),
) -> dict[str, Any]:
    rows = list(reports)

    if base_decision.get('schema') != 'vl.independent-completion-decision/1':
        return _consensus_decision(
            'HOLD', 'BASE_DECISION_SCHEMA_INVALID', base_decision, rows, policy=policy
        )

    decision_sha = str(base_decision.get('decision_sha256') or '')
    try:
        _require_sha('decision_sha256', decision_sha)
    except ValueError:
        return _consensus_decision(
            'HOLD', 'BASE_DECISION_DIGEST_INVALID', base_decision, rows, policy=policy
        )

    if base_decision.get('builder_self_report_trusted') is not False:
        return _consensus_decision(
            'HOLD', 'BASE_DECISION_INVARIANT_INVALID', base_decision, rows, policy=policy
        )
    if base_decision.get('production_locked') is not True:
        return _consensus_decision(
            'HOLD', 'BASE_DECISION_INVARIANT_INVALID', base_decision, rows, policy=policy
        )

    if not isinstance(policy.minimum_validators, int) or isinstance(policy.minimum_validators, bool) or policy.minimum_validators < 2:
        return _consensus_decision(
            'HOLD', 'INVALID_CONSENSUS_POLICY', base_decision, rows, policy=policy,
            errors=['minimum_validators must be >= 2'],
        )
    if not isinstance(policy.minimum_methods, int) or isinstance(policy.minimum_methods, bool) or policy.minimum_methods < 1:
        return _consensus_decision(
            'HOLD', 'INVALID_CONSENSUS_POLICY', base_decision, rows, policy=policy,
            errors=['minimum_methods must be >= 1'],
        )
    if (
        not isinstance(policy.maximum_confidence_spread, (int, float))
        or isinstance(policy.maximum_confidence_spread, bool)
        or not math.isfinite(float(policy.maximum_confidence_spread))
        or not 0.0 <= float(policy.maximum_confidence_spread) <= 1.0
    ):
        return _consensus_decision(
            'HOLD', 'INVALID_CONSENSUS_POLICY', base_decision, rows, policy=policy,
            errors=['maximum_confidence_spread must be finite and within [0,1]'],
        )

    if base_decision.get('status') == 'FAIL':
        return _consensus_decision(
            'FAIL', 'BASE_COMPLETION_FAILED', base_decision, rows, policy=policy
        )
    if base_decision.get('status') != 'PASS':
        return _consensus_decision(
            'HOLD', 'BASE_COMPLETION_NOT_PASS', base_decision, rows, policy=policy
        )

    if len(rows) < policy.minimum_validators:
        return _consensus_decision(
            'HOLD', 'VERIFIER_QUORUM_NOT_MET', base_decision, rows, policy=policy
        )

    validator_ids = [r.validator_id.strip() for r in rows]
    if any(not x for x in validator_ids):
        return _consensus_decision(
            'HOLD', 'VERIFIER_ID_REQUIRED', base_decision, rows, policy=policy
        )
    if len(set(validator_ids)) != len(validator_ids):
        return _consensus_decision(
            'HOLD', 'DUPLICATE_VERIFIER_ID', base_decision, rows, policy=policy
        )

    errors: list[str] = []
    for report in rows:
        if not report.executor_id.strip():
            errors.append(f'{report.validator_id}:EXECUTOR_ID_REQUIRED')
        if report.validator_id.strip() == report.executor_id.strip():
            errors.append(f'{report.validator_id}:SELF_VALIDATION_FORBIDDEN')
        if report.decision_sha256 != decision_sha:
            errors.append(f'{report.validator_id}:DECISION_BINDING_MISMATCH')
        if report.status not in ALLOWED_VERIFIER_STATES:
            errors.append(f'{report.validator_id}:INVALID_VERIFIER_STATE')
        if not report.evidence_fresh:
            errors.append(f'{report.validator_id}:STALE_VERIFIER_EVIDENCE')
        if not _addressable_ref(report.evidence_ref):
            errors.append(f'{report.validator_id}:EVIDENCE_REF_INVALID')
        if not report.method_id.strip():
            errors.append(f'{report.validator_id}:METHOD_ID_REQUIRED')
        if (
            not isinstance(report.confidence, (int, float))
            or isinstance(report.confidence, bool)
            or not math.isfinite(float(report.confidence))
            or not 0.0 <= float(report.confidence) <= 1.0
        ):
            errors.append(f'{report.validator_id}:CONFIDENCE_INVALID')

    if errors:
        return _consensus_decision(
            'HOLD', 'VERIFIER_REPORT_INVALID', base_decision, rows, policy=policy, errors=errors
        )

    methods = {r.method_id for r in rows}
    if len(methods) < policy.minimum_methods:
        return _consensus_decision(
            'HOLD', 'VERIFIER_METHOD_DIVERSITY_NOT_MET', base_decision, rows, policy=policy
        )

    evidence_refs = [r.evidence_ref for r in rows]
    if policy.require_unique_evidence_refs and len(set(evidence_refs)) != len(evidence_refs):
        return _consensus_decision(
            'HOLD', 'VERIFIER_EVIDENCE_NOT_INDEPENDENT', base_decision, rows, policy=policy
        )

    states = [r.status for r in rows]
    if 'FAIL' in states:
        return _consensus_decision(
            'FAIL', 'VERIFIER_NEGATIVE_FINDING', base_decision, rows, policy=policy
        )
    if 'HOLD' in states:
        return _consensus_decision(
            'HOLD', 'VERIFIER_HOLD_OR_DISAGREEMENT', base_decision, rows, policy=policy
        )
    if any(state != 'PASS' for state in states):
        return _consensus_decision(
            'HOLD', 'VERIFIER_DISAGREEMENT', base_decision, rows, policy=policy
        )

    confidences = [float(r.confidence) for r in rows]
    spread = max(confidences) - min(confidences)
    if spread > float(policy.maximum_confidence_spread):
        return _consensus_decision(
            'HOLD', 'VERIFIER_CONFIDENCE_DISAGREEMENT', base_decision, rows, policy=policy
        )

    return _consensus_decision(
        'PASS', 'INDEPENDENT_CONSENSUS_PASS', base_decision, rows, policy=policy
    )
