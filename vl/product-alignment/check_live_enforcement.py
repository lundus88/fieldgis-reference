#!/usr/bin/env python3
from pathlib import Path
import sys

MIGRATION = Path('vl/migrations/20260831_product_alignment_live_gate.sql')
COMPILER_FIX = Path('vl/migrations/20260831_fix_manual_coordinate_routing.sql')

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

if not COMPILER_FIX.exists():
    print(f'COMPILER ROUTING REGRESSION: FAIL - missing {COMPILER_FIX}')
    raise SystemExit(1)

compiler = COMPILER_FIX.read_text()

# Manual coordinate words must not be part of the GPS trigger expression.
gps_clause_start = compiler.find("if v_prompt ~ '(")
gps_clause_end = compiler.find("then\n    v_caps := array_append(v_caps,'gps');", gps_clause_start)
if gps_clause_start < 0 or gps_clause_end < 0:
    print('COMPILER ROUTING REGRESSION: FAIL - GPS inference clause not found')
    raise SystemExit(1)
gps_clause = compiler[gps_clause_start:gps_clause_end]
for forbidden in ('coordinate|', 'coordinates|', 'koordinat|', '|coordinate', '|coordinates', '|koordinat'):
    if forbidden in gps_clause:
        print(f'COMPILER ROUTING REGRESSION: FAIL - manual coordinate term still forces GPS: {forbidden}')
        raise SystemExit(1)

# Explicit location/GPS intent must still request the GPS capability.
for required_gps_signal in ('\\mgps\\M', '\\mgnss\\M', 'current location', 'device location', 'lokasi semasa'):
    if required_gps_signal not in gps_clause:
        print(f'COMPILER ROUTING REGRESSION: FAIL - missing explicit GPS signal: {required_gps_signal}')
        raise SystemExit(1)

if "'compiler_version','1.6'" not in compiler:
    print('COMPILER ROUTING REGRESSION: FAIL - compiler version 1.6 marker missing')
    raise SystemExit(1)

print('LIVE PRODUCT ALIGNMENT: PASS')
print('COMPILER ROUTING REGRESSION: PASS')
