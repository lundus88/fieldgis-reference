#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATOR = ROOT / "validate_product_alignment.py"
CASES = [
    ("tests/valid.json", 0),
    ("tests/invalid_missing_intent.json", 1),
    ("tests/invalid_unmapped_p0.json", 1),
    ("tests/invalid_contradiction.json", 1),
]

failures=[]
for rel, expected in CASES:
    path=ROOT/rel
    result=subprocess.run([sys.executable, str(VALIDATOR), str(path)], capture_output=True, text=True)
    print(f"[{rel}] rc={result.returncode}")
    if result.stdout.strip(): print(result.stdout.strip())
    if result.returncode != expected:
        failures.append(f"{rel}: expected rc {expected}, got {result.returncode}")

if failures:
    print("PRODUCT ALIGNMENT REGRESSION: FAIL")
    for f in failures: print(f"- {f}")
    sys.exit(1)
print("PRODUCT ALIGNMENT REGRESSION: PASS")
