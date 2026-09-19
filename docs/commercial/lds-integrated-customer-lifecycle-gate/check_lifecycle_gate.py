#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-integrated-customer-lifecycle-gate")
errors=[]
for f in ["README.md","contract.json","lifecycle_gate.py","test_lifecycle_gate.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.integrated-customer-lifecycle-gate/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in [
      "must not create a second source of truth",
      "Payment evidence alone",
      "Material scope change requires approved Change Request",
      "QA PASS requires QA evidence",
      "Production deployment authority remains separate"
    ]:
      if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Integrated Customer Lifecycle Gate: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Integrated Customer Lifecycle Gate: PASS")
