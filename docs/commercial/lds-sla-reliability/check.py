#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-sla-reliability")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.sla-reliability/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    if d.get("automatic_service_credit_authorized") is not False: errors.append("service credit must remain false")
    text=" ".join(d.get("invariants",[]))
    for t in ["approved and versioned","monitoring or incident evidence","never automatic","defined customer impact","must not exceed","does not itself authorize"]:
        if t not in text: errors.append(f"missing invariant {t}")
if errors:
    print("LD SLA Reliability: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD SLA Reliability: PASS")
