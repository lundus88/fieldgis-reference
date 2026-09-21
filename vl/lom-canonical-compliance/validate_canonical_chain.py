#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name('canonical-chain.json')

REQUIRED_AUTHORITY = {
    'autonomous_ceiling': 'PREPARE_PR',
    'production_authority': 'HUMAN_ONLY',
    'protected_main_merge': 'HUMAN_ONLY',
    'self_approval': 'FORBIDDEN',
    'missing_evidence': 'HOLD',
    'unknown_authority': 'HOLD',
}

REQUIRED_STAGE_SEQUENCE = [
    '4.3', '4.4', '4.5', '5.0', '6.0', '6.1', '6.2', '6.3', '6.3.1',
    '6.3.2', '6.3.3', '6.3.4', '6.3.5', '6.3.6', '6.4', '6.5', '6.6',
    '6.7', '6.8', '6.9', '6.9.2', '6.9.3', '6.10', '6.11', '6.12',
]


def fail(message: str) -> None:
    raise SystemExit(f'FAIL: {message}')


def validate(data: dict) -> None:
    if data.get('schema') != 'lom.canonical-compliance-chain/1':
        fail('unsupported canonical chain schema')
    if data.get('status') != 'DEVELOPMENT_NON_PRODUCTION':
        fail('canonical chain must remain DEVELOPMENT_NON_PRODUCTION')

    authority = data.get('authority') or {}
    for key, expected in REQUIRED_AUTHORITY.items():
        if authority.get(key) != expected:
            fail(f'authority invariant weakened: {key}')

    stages = data.get('canonical_stages') or []
    if not stages:
        fail('canonical stages missing')

    ids = [stage.get('id') for stage in stages]
    owners = [stage.get('owner') for stage in stages]
    artifacts = [stage.get('artifact') for stage in stages]
    if ids != REQUIRED_STAGE_SEQUENCE:
        fail('canonical stage sequence incomplete, reordered, or contains an unexpected stage')
    if len(ids) != len(set(ids)):
        fail('duplicate canonical stage id')
    if len(owners) != len(set(owners)):
        fail('duplicate canonical owner')
    if len(artifacts) != len(set(artifacts)):
        fail('duplicate canonical artifact ownership')

    for stage in stages:
        if not stage.get('id') or not stage.get('owner') or not stage.get('artifact'):
            fail('incomplete canonical stage declaration')
        if not (ROOT / stage['artifact']).is_file():
            fail(f"missing canonical artifact: {stage['artifact']}")

    pending = data.get('pending_external_stages') or []
    pending_ids = {item.get('id') for item in pending}
    if set(ids) & pending_ids:
        fail('pending stage must not be promoted to canonical before merge')
    for item in pending:
        if not item.get('id') or not item.get('owner') or not item.get('tracking_pr'):
            fail('pending stage declaration incomplete')
        if item.get('merge_required_before_canonical') is not True:
            fail('pending stage must require merge before canonical promotion')

    invariants = data.get('critical_invariants') or []
    if not invariants:
        fail('critical invariants missing')
    for invariant in invariants:
        path = ROOT / invariant['artifact']
        if not path.is_file():
            fail(f'missing invariant artifact: {invariant["artifact"]}')
        text = path.read_text(encoding='utf-8')
        tokens = invariant.get('tokens') or []
        if not tokens:
            fail(f'critical invariant tokens missing for {invariant["artifact"]}')
        for token in tokens:
            if token not in text:
                fail(f'critical invariant missing from {invariant["artifact"]}: {token}')


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    validate(data)
    print('LOM CANONICAL COMPLIANCE CHAIN: PASS')
    print(f"CANONICAL STAGES: {len(data['canonical_stages'])}")
    print('AUTONOMOUS CEILING: PREPARE_PR')
    print('PRODUCTION AUTHORITY: HUMAN_ONLY')
    print('PROTECTED MAIN MERGE: HUMAN_ONLY')
    print('SELF APPROVAL: FORBIDDEN')
    if data.get('pending_external_stages'):
        pending = ', '.join(item['id'] for item in data['pending_external_stages'])
        print(f'PENDING EXTERNAL STAGES: {pending}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
