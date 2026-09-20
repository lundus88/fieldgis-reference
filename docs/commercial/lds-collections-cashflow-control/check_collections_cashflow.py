#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-collections-cashflow-control")
errors=[]
for f in ["README.md","contract.json","collections_cashflow.py","test_collections_cashflow.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.collections-cashflow-control/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["Overdue status must never","PAID requires authoritative","Disputed invoices","Partial payment","cannot alter invoice amount"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Collections Cashflow Control: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Collections Cashflow Control: PASS")
