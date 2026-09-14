#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'vl/lom-operational-safety/action-registry.json'
RUNTIME = ROOT / 'vl/lom-self-improvement-runtime/self_improvement_runtime.py'
ORCHESTRATOR = ROOT / 'vl/lom-continuous-improvement/orchestrator.py'
COCKPIT = ROOT / 'vl/lom-daily-ops-cockpit/cockpit.py'

REQUIRED_HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE', 'PRODUCTION_RELEASE', 'PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING', 'AUTH_SECURITY_POLICY_CHANGE', 'DATA_DELETION',
    'CUSTOMER_COMMITMENT', 'BID_SUBMISSION', 'PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT', 'FINANCIAL_COMMITMENT'
}


def fail(msg):
    print(f'FAIL: {msg}')
    raise SystemExit(1)


def main():
    registry = json.loads(REGISTRY.read_text())
    if registry.get('default_decision') != 'DENY':
        fail('action registry must default DENY')
    if registry.get('production_locked') is not True:
        fail('production lock must be true')
    registered = set(registry.get('human_only_actions', []))
    missing = sorted(REQUIRED_HUMAN_ONLY - registered)
    if missing:
        fail('authority registry drift; missing HUMAN_ONLY: ' + ', '.join(missing))

    for path in (RUNTIME, ORCHESTRATOR, COCKPIT):
        text = path.read_text()
        for action in REQUIRED_HUMAN_ONLY:
            if action not in text:
                fail(f'{path.relative_to(ROOT)} missing HUMAN_ONLY invariant: {action}')

    print('LOM SECURITY AUTHORITY ALIGNMENT: PASS')
    print('PRODUCTION AUTHORITY: HUMAN_ONLY')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
