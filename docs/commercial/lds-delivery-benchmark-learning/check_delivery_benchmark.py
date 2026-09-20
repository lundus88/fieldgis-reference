#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-delivery-benchmark-learning")
errors=[]
for f in ["README.md","contract.json","delivery_benchmark.py","test_delivery_benchmark.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.delivery-benchmark-learning/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["sample size","variance or spread","Customer-caused dependency delay","must not overwrite","planning evidence only"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Delivery Benchmark Learning: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Delivery Benchmark Learning: PASS")
