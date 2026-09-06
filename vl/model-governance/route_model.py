#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


class ModelRoutingBlocked(RuntimeError):
    pass


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def validate_registry(registry):
    if registry.get('schema') != 'vl.model-registry/1':
        raise ValueError('unsupported model registry schema')
    if not isinstance(registry.get('version'), int) or registry['version'] < 1:
        raise ValueError('registry version must be a positive integer')
    models = registry.get('models')
    if not isinstance(models, list) or not models:
        raise ValueError('models are required')
    ids = set()
    for model in models:
        mid = str(model.get('id') or '')
        if not mid or mid in ids:
            raise ValueError('model ids must be unique and non-empty')
        ids.add(mid)
        if model.get('status') not in ('active', 'deprecated', 'unavailable'):
            raise ValueError(f'invalid status for {mid}')
        if not isinstance(model.get('task_classes'), list) or not model['task_classes']:
            raise ValueError(f'task_classes required for {mid}')
        privacy = model.get('privacy') or {}
        if privacy.get('retention') not in ('none', 'session', '30_days'):
            raise ValueError(f'invalid retention for {mid}')
        if privacy.get('training') not in ('disabled', 'enabled'):
            raise ValueError(f'invalid training policy for {mid}')
        for key in ('max_input_tokens', 'max_output_tokens', 'max_autonomy_horizon', 'priority'):
            if not isinstance(model.get(key), int) or model[key] < 0:
                raise ValueError(f'{key} must be a non-negative integer for {mid}')
        cost = model.get('estimated_cost_per_1k_tokens')
        if not isinstance(cost, (int, float)) or cost < 0:
            raise ValueError(f'invalid cost for {mid}')
    return True


def privacy_compatible(model, request):
    sensitive = request.get('data_class') in {'secret', 'credential', 'customer_private', 'proprietary_dataset', 'production_data'}
    privacy = model['privacy']
    if sensitive:
        return privacy['retention'] == 'none' and privacy['training'] == 'disabled'
    allowed_retention = request.get('max_retention', 'none')
    rank = {'none': 0, 'session': 1, '30_days': 2}
    if allowed_retention not in rank:
        raise ValueError('invalid max_retention')
    return rank[privacy['retention']] <= rank[allowed_retention] and privacy['training'] == 'disabled'


def route_model(registry, request):
    validate_registry(registry)
    required = ('task_class', 'data_class', 'input_tokens', 'output_tokens', 'cost_ceiling', 'autonomy_horizon')
    for key in required:
        if key not in request:
            raise ModelRoutingBlocked(f'MODEL_ROUTING_BLOCKED: missing {key}')
    if not isinstance(request['input_tokens'], int) or request['input_tokens'] < 0:
        raise ModelRoutingBlocked('MODEL_ROUTING_BLOCKED: invalid input_tokens')
    if not isinstance(request['output_tokens'], int) or request['output_tokens'] < 0:
        raise ModelRoutingBlocked('MODEL_ROUTING_BLOCKED: invalid output_tokens')
    if not isinstance(request['cost_ceiling'], (int, float)) or request['cost_ceiling'] < 0:
        raise ModelRoutingBlocked('MODEL_ROUTING_BLOCKED: invalid cost_ceiling')
    if not isinstance(request['autonomy_horizon'], int) or request['autonomy_horizon'] < 0:
        raise ModelRoutingBlocked('MODEL_ROUTING_BLOCKED: invalid autonomy_horizon')

    candidates = []
    rejected = []
    for model in registry['models']:
        reasons = []
        if model['status'] != 'active':
            reasons.append(f"status:{model['status']}")
        if request['task_class'] not in model['task_classes']:
            reasons.append('task_class')
        if request['input_tokens'] > model['max_input_tokens']:
            reasons.append('input_tokens')
        if request['output_tokens'] > model['max_output_tokens']:
            reasons.append('output_tokens')
        if request['autonomy_horizon'] > model['max_autonomy_horizon']:
            reasons.append('autonomy_horizon')
        estimated_total_cost = ((request['input_tokens'] + request['output_tokens']) / 1000.0) * model['estimated_cost_per_1k_tokens']
        if estimated_total_cost > request['cost_ceiling']:
            reasons.append('cost_ceiling')
        try:
            if not privacy_compatible(model, request):
                reasons.append('privacy')
        except ValueError as exc:
            raise ModelRoutingBlocked(f'MODEL_ROUTING_BLOCKED: {exc}') from exc
        if reasons:
            rejected.append({'model_id': model['id'], 'reasons': reasons})
        else:
            candidates.append((model, estimated_total_cost))

    if not candidates:
        raise ModelRoutingBlocked('MODEL_ROUTING_BLOCKED: no approved model satisfies policy')

    candidates.sort(key=lambda item: (item[0]['priority'], item[0]['id']))
    selected, estimated_cost = candidates[0]
    fallbacks = [item[0]['id'] for item in candidates[1:]]

    evidence = {
        'schema': 'vl.model-routing-evidence/1',
        'registry_id': registry['registry_id'],
        'registry_version': registry['version'],
        'request_sha256': canonical_hash(request),
        'selected_model_id': selected['id'],
        'fallback_chain': fallbacks,
        'estimated_cost': round(estimated_cost, 8),
        'rejected': sorted(rejected, key=lambda x: x['model_id']),
        'deterministic': True,
        'production_locked': True,
    }
    evidence['decision_sha256'] = canonical_hash(evidence)
    return evidence


def main():
    if len(sys.argv) != 3:
        print('usage: route_model.py <registry.json> <request.json>', file=sys.stderr)
        return 2
    try:
        registry = json.loads(Path(sys.argv[1]).read_text())
        request = json.loads(Path(sys.argv[2]).read_text())
        print(json.dumps(route_model(registry, request), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
