#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    'vl/LOM_V1.md',
    'vl/context-governance/default-context-policy.json',
    'vl/completion-governance/independent_validator.py',
    'vl/model-governance/route_model.py',
    'vl/execution-governance/execution_pool_policy.py',
    'vl/remediation-governance/remediation_policy.py',
    'vl/multi-agent-governance/delegation_policy.py',
    'vl/connector-governance/connector-registry.json',
    'vl/golden-workflow/run_golden_workflow.py',
    'vl/lom-4-evolution/LOM2_GATE_B.md',
    'vl/lom-gate-c-runtime/README.md',
    'vl/lom-gate-d-remediation/README.md',
    'vl/lom-gate-e-orchestrator/README.md',
    'vl/lom-mission-control/README.md',
    'vl/lom-business-os/README.md',
    'vl/lom-autonomous-org/README.md',
    'vl/lom-controlled-validation/README.md',
    'vl/lom-operational-safety/README.md',
    'vl/lom-operational-safety/action-registry.json',
    'vl/lom-operational-safety/action_registry.py',
    'vl/lom-operational-safety/delegation.py',
    'vl/lom-operational-safety/evidence_replay.py',
    'vl/lom-operational-safety/event_ledger.py',
]

WORKFLOWS = [
    '.github/workflows/lom-core-governance.yml',
    '.github/workflows/lom-2-bounded-autonomy.yml',
    '.github/workflows/lom-2-gate-c-runtime.yml',
    '.github/workflows/lom-2-gate-d-remediation.yml',
    '.github/workflows/lom-2-gate-e-orchestrator.yml',
    '.github/workflows/lom-2-gate-f-mission-control.yml',
    '.github/workflows/lom-3-business-os.yml',
    '.github/workflows/lom-4-autonomous-org.yml',
    '.github/workflows/lom-4-controlled-validation.yml',
    '.github/workflows/lom-master-compliance.yml',
]

TEXT_ASSERTIONS = {
    'vl/LOM_V1.md': [
        'Request → Plan → Execute → Verify → Human Approval → Release → Audit',
        'Production approval is human-only',
    ],
    'vl/lom-4-evolution/LOM2_GATE_B.md': ['bounded'],
    'vl/lom-gate-c-runtime/README.md': ['Multi-Agent Task Runtime'],
    'vl/lom-gate-d-remediation/README.md': ['reversible', 'non-production'],
    'vl/lom-gate-e-orchestrator/README.md': ['Goal-to-Outcome'],
    'vl/lom-mission-control/README.md': ['Director Mission Control'],
    'vl/lom-business-os/README.md': ['AI Business Operating System'],
    'vl/lom-autonomous-org/README.md': ['Autonomous Digital Organization'],
    'vl/lom-controlled-validation/README.md': ['Controlled Operational Validation'],
    'vl/lom-operational-safety/README.md': ['Operational Safety Hardening', 'default deny', 'AppendOnlyEventLedger'],
}


def fail(message: str) -> None:
    print(f'FAIL: {message}')
    raise SystemExit(1)


def main() -> int:
    for rel in REQUIRED + WORKFLOWS:
        if not (ROOT / rel).is_file():
            fail(f'missing required artifact: {rel}')

    for rel, needles in TEXT_ASSERTIONS.items():
        text = (ROOT / rel).read_text(encoding='utf-8')
        for needle in needles:
            if needle not in text:
                fail(f'{rel} missing invariant text: {needle}')

    runtime = (ROOT / 'vl/lom-autonomous-org/org_runtime.py').read_text(encoding='utf-8')
    for needle in [
        'HUMAN_ONLY',
        'UNKNOWN_OR_UNDELEGATED_AUTHORITY',
        'EVIDENCE_NOT_READY',
        'PRODUCTION_BOUNDARY',
        'PROPOSE_ONLY',
    ]:
        if needle not in runtime:
            fail(f'LOM 4 runtime missing fail-closed control: {needle}')

    safety_files = [
        ROOT / 'vl/lom-operational-safety/action_registry.py',
        ROOT / 'vl/lom-operational-safety/delegation.py',
        ROOT / 'vl/lom-operational-safety/evidence_replay.py',
        ROOT / 'vl/lom-operational-safety/event_ledger.py',
    ]
    safety_text = '\n'.join(path.read_text(encoding='utf-8') for path in safety_files)
    for needle in [
        'UNREGISTERED_ACTION',
        'EXECUTOR_VALIDATOR_COLLISION',
        'REMEDIATOR_VALIDATOR_COLLISION',
        'DELEGATION_EXPIRED',
        'DELEGATION_CAPABILITY_WIDENED',
        'ATTEMPT_BUDGET_EXHAUSTED',
        'DUPLICATE_OR_REPLAY',
        'STALE_EVIDENCE',
        'CONTRADICTORY_EVIDENCE',
        'APPEND_ONLY_LEDGER',
        'UNKNOWN_STATE',
    ]:
        if needle not in safety_text:
            fail(f'LOM 4.1 safety control missing: {needle}')

    completion = (ROOT / 'vl/completion-governance/independent_validator.py').read_text(encoding='utf-8')
    if "'builder_self_report_trusted': False" not in completion:
        fail('independent completion validator does not reject builder self-certification')

    print('LOM MASTER COMPLIANCE: PASS')
    print('LOM 1.0: PRESENT')
    print('LOM 2.0: PRESENT')
    print('LOM 3.0: PRESENT')
    print('LOM 4.0: PRESENT')
    print('LOM 4.1: PRESENT')
    print('PRODUCTION AUTHORITY: NOT GRANTED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
