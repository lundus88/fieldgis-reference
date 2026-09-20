#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-reusable-solution-catalog")
errors=[]
for f in ["README.md","contract.json","solution_catalog.py","test_solution_catalog.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.reusable-solution-catalog/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["single successful run","Deprecated components","Builder compatibility","licensing or ownership","must never be embedded"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Reusable Solution Catalog: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Reusable Solution Catalog: PASS")
