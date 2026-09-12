#!/usr/bin/env python3
import hashlib
import json
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
        decisions.append({
            'resource_type': resource_type,
            'resource': resource,
            'data_class': data_class,
            'decision': verdict['decision'],
            'rule_ids': verdict['rule_ids'],
            'content_sha256': sha256_text(content),
        })
        if verdict['decision'] == 'allow':
            allowed.append({'resource_type': resource_type, 'resource': resource, 'data_class': data_class, 'content': content})
    return {'context': allowed, 'manifest': {
        'schema': 'vl.context-provenance/1',
        'policy_id': policy['policy_id'],
        'policy_version': policy['version'],
        'default_decision': policy['default_decision'],
        'resource_decisions': decisions,
        'allowed_count': len(allowed),
        'denied_count': len(decisions) - len(allowed),
        'secret_values_recorded': False,
    }}
