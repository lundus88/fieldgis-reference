#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-support-maintenance-plans")
errors=[]
for f in ["README.md","contract.json","support_plan_engine.py","test_support_plan_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.support-maintenance-plans/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain unauthorized")
    inv=" ".join(d.get("invariants",[]))
    for token in ["response target from resolution target","Third-party hosting","Recurring charges","Agreed-scope defects","Change Request"]:
        if token not in inv: errors.append(f"missing invariant {token}")
if errors:
    print("LDS Support Maintenance Plans: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Support Maintenance Plans: PASS")
