#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-project-profitability-capacity")
errors=[]
for f in ["README.md","contract.json","profitability_capacity.py","test_profitability_capacity.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.project-profitability-capacity/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain unauthorized")
    inv=" ".join(d.get("invariants",[]))
    for token in [
      "evidence-backed revenue and cost inputs",
      "Internal AI/build failures",
      "must not automatically change a customer price",
      "Capacity HOLD",
      "internal planning metric"
    ]:
      if token not in inv: errors.append(f"missing invariant {token}")
if errors:
    print("LDS Project Profitability Capacity: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Project Profitability Capacity: PASS")
