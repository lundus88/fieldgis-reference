#!/usr/bin/env python3
from pathlib import Path
import sys

MIGRATION = Path('vl/migrations/20260831_product_alignment_live_gate.sql')

required = {
    'activation policy': 'private.product_alignment_policy',
    'DB validator': 'private.validate_product_alignment',
    'legacy compatibility selector': 'private.requires_product_alignment',
    'factory run trigger': 'trg_factory_runs_product_alignment',
    'factory run enforcement': 'private.enforce_product_alignment_on_factory_run',
    'internal certification exemption': 'certification_depth_run',
    'runner claim defense': 'product_alignment_rejected',
    'runner enforcement marker': 'product_alignment_enforced',
    'human contract payload path': "spec->'product_alignment'",
}

if not MIGRATION.exists():
    print(f'LIVE PRODUCT ALIGNMENT: FAIL - missing {MIGRATION}')
    raise SystemExit(1)

text = MIGRATION.read_text()
missing = [label for label, needle in required.items() if needle not in text]
if missing:
    print('LIVE PRODUCT ALIGNMENT: FAIL')
    for label in missing:
        print(f'- missing enforcement invariant: {label}')
    raise SystemExit(1)

# The execution boundary must not weaken the existing production lock.
for needle in ("target_environment='production'", 'production_locked is distinct from true'):
    if needle not in text:
        print(f'LIVE PRODUCT ALIGNMENT: FAIL - production lock invariant missing: {needle}')
        raise SystemExit(1)

print('LIVE PRODUCT ALIGNMENT: PASS')
