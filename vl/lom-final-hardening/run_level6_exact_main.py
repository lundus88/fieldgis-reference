#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VL = ROOT / 'vl'


def run(cmd: list[str], *, cwd: Path = ROOT) -> None:
    print(f"+ {' '.join(cmd)}  [cwd={cwd.relative_to(ROOT) if cwd != ROOT else '.'}]")
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    stage_dirs = sorted(
        p for p in VL.glob('lom-6-*')
        if p.is_dir() and p.name != 'lom-final-hardening'
    )
    if not stage_dirs:
        raise SystemExit('FAIL: no LOM 6.x stage directories found')

    executed: list[str] = []
    missing_tests: list[str] = []

    for stage_dir in stage_dirs:
        tests = sorted(stage_dir.glob('test*.py'))
        if not tests:
            missing_tests.append(stage_dir.name)
            continue
        run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', '.', '-p', 'test*.py', '-v'],
            cwd=stage_dir,
        )
        executed.append(stage_dir.name)

    run([sys.executable, 'vl/lom-canonical-compliance/validate_canonical_chain.py'])
    run([sys.executable, '-m', 'unittest', '-v', 'vl/lom-canonical-compliance/test_canonical_chain.py'])

    required_functional = {
        'lom-6-ai-control-plane',
        'lom-6-2-real-measurement-instrumentation',
        'lom-6-3-telemetry-collection-pilot',
        'lom-6-3-1-live-readonly-evidence-adapter',
        'lom-6-3-2-technical-metrics-artifact-contract',
        'lom-6-3-3-metric-semantics-registry',
        'lom-6-3-4-evidence-replay-reproducibility',
        'lom-6-3-5-evidence-lineage-chain-of-custody',
        'lom-6-3-6-critical-safety-propagation',
        'lom-6-4-operational-intelligence-dashboard',
        'lom-6-5-evidence-driven-alerts-director-brief',
        'lom-6-6-governed-remediation-planner',
        'lom-6-7-autonomous-validation-sandbox',
        'lom-6-8-governed-pr-evidence-promotion',
        'lom-6-9-human-approval-decision-package',
        'lom-6-9-2-human-approval-receipt',
        'lom-6-9-3-approval-consumption-ledger',
        'lom-6-12-cognitive-integration',
    }
    missing_required = sorted(required_functional - set(executed))
    if missing_required:
        print('FAIL: required LOM 6.x functional suites were not executed:')
        for name in missing_required:
            print(f'- {name}')
        return 1

    print('LOM LEVEL 6 EXACT-MAIN REGRESSION: PASS')
    print(f'FUNCTIONAL SUITES EXECUTED: {len(executed)}')
    if missing_tests:
        print('CONTRACT-ONLY / NO DISCOVERED TEST FILES:')
        for name in missing_tests:
            print(f'- {name}')
    print('AUTONOMOUS CEILING: PREPARE_PR')
    print('PRODUCTION AUTHORITY: HUMAN_ONLY')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
