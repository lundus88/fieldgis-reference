#!/usr/bin/env python3
import fnmatch
import json
import sys
from pathlib import Path

REQUIRED_AUDIT = {
    'record_policy_version': True,
    'record_resource_class': True,
    'record_decision': True,
    'record_secret_values': False,
}


def fail(message):
    raise ValueError(message)


def validate_policy(doc):
    if doc.get('schema') != 'vl.context-policy/1':
        fail('unsupported context policy schema')
    if doc.get('default_decision') != 'deny':
        fail('default_decision must be deny')
    if not str(doc.get('policy_id') or '').strip():
        fail('policy_id is required')
    if not isinstance(doc.get('version'), int) or doc['version'] < 1:
        fail('version must be a positive integer')

    sensitive = doc.get('sensitive_classes')
    if not isinstance(sensitive, list) or not sensitive or len(set(sensitive)) != len(sensitive):
        fail('sensitive_classes must be a non-empty unique list')

    rules = doc.get('rules')
    if not isinstance(rules, list) or not rules:
        fail('rules are required')
    seen = set()
    for rule in rules:
        rid = str(rule.get('id') or '').strip()
        if not rid or rid in seen:
            fail('rule ids must be unique and non-empty')
        seen.add(rid)
        if rule.get('effect') not in ('allow', 'deny'):
            fail(f'rule {rid} has invalid effect')
        if rule.get('resource_type') not in ('repo_path', 'connector_resource', 'generated_artifact', 'prompt_attachment'):
            fail(f'rule {rid} has invalid resource_type')
        for key in ('pattern', 'data_class', 'reason'):
            if not str(rule.get(key) or '').strip():
                fail(f'rule {rid} missing {key}')

    audit = doc.get('audit') or {}
    for key, expected in REQUIRED_AUDIT.items():
        if audit.get(key) is not expected:
            fail(f'audit.{key} must be {str(expected).lower()}')
    return True


def decide(doc, resource_type, resource, data_class):
    validate_policy(doc)
    matches = []
    for rule in doc['rules']:
        if rule['resource_type'] != resource_type:
            continue
        if rule['data_class'] not in (data_class, '*'):
            continue
        if fnmatch.fnmatchcase(resource, rule['pattern']):
            matches.append(rule)

    denies = [r for r in matches if r['effect'] == 'deny']
    if denies:
        return {'decision': 'deny', 'rule_ids': [r['id'] for r in denies], 'reason': 'explicit deny rule matched'}
    allows = [r for r in matches if r['effect'] == 'allow']
    if allows and data_class not in doc['sensitive_classes']:
        return {'decision': 'allow', 'rule_ids': [r['id'] for r in allows], 'reason': 'explicit allow rule matched'}
    if allows and data_class in doc['sensitive_classes']:
        return {'decision': 'deny', 'rule_ids': [r['id'] for r in allows], 'reason': 'sensitive class requires explicit deny-safe handling'}
    return {'decision': 'deny', 'rule_ids': [], 'reason': 'no explicit allow; default deny'}


def main():
    if len(sys.argv) not in (2, 5):
        print('usage: validate_context_policy.py <policy.json> [resource_type resource data_class]', file=sys.stderr)
        return 2
    try:
        doc = json.loads(Path(sys.argv[1]).read_text())
        validate_policy(doc)
        if len(sys.argv) == 5:
            print(json.dumps(decide(doc, sys.argv[2], sys.argv[3], sys.argv[4]), sort_keys=True))
        else:
            print('CONTEXT POLICY: PASS')
        return 0
    except Exception as exc:
        print(f'CONTEXT POLICY: FAIL - {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
