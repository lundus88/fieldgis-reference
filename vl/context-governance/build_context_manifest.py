#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path
from validate_context_policy import validate_policy, decide


def sha256_text(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def build_context(policy, resources):
    validate_policy(policy)
    allowed = []
    decisions = []
    for item in resources:
        resource_type = item.get('resource_type')
        resource = item.get('resource')
        data_class = item.get('data_class')
        content = item.get('content')
        if not all(isinstance(x, str) and x for x in (resource_type, resource, data_class, content)):
            raise ValueError('each resource requires resource_type, resource, data_class and content')
        verdict = decide(policy, resource_type, resource, data_class)
        record = {
            'resource_type': resource_type,
            'resource': resource,
            'data_class': data_class,
            'decision': verdict['decision'],
            'rule_ids': verdict['rule_ids'],
            'content_sha256': sha256_text(content),
        }
        decisions.append(record)
        if verdict['decision'] == 'allow':
            allowed.append({
                'resource_type': resource_type,
                'resource': resource,
                'data_class': data_class,
                'content': content,
            })

    manifest = {
        'schema': 'vl.context-provenance/1',
        'policy_id': policy['policy_id'],
        'policy_version': policy['version'],
        'default_decision': policy['default_decision'],
        'resource_decisions': decisions,
        'allowed_count': len(allowed),
        'denied_count': len(decisions) - len(allowed),
        'secret_values_recorded': False,
    }
    return {'context': allowed, 'manifest': manifest}


def main():
    if len(sys.argv) != 4:
        print('usage: build_context_manifest.py <policy.json> <resources.json> <output.json>', file=sys.stderr)
        return 2
    try:
        policy = json.loads(Path(sys.argv[1]).read_text())
        resources = json.loads(Path(sys.argv[2]).read_text())
        if not isinstance(resources, list):
            raise ValueError('resources must be a list')
        result = build_context(policy, resources)
        Path(sys.argv[3]).write_text(json.dumps(result, indent=2))
        print(f"CONTEXT BUILD: PASS allowed={result['manifest']['allowed_count']} denied={result['manifest']['denied_count']}")
        return 0
    except Exception as exc:
        print(f'CONTEXT BUILD: FAIL - {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
