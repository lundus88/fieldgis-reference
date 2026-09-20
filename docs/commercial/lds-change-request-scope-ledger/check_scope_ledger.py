#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-change-request-scope-ledger")
errors=[]
for f in ["README.md","contract.json","change_request_engine.py","test_change_request_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.change-request-scope-ledger/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain unauthorized")
    inv=" ".join(d.get("invariants",[]))
    for token in [
        "Approved scope snapshot remains immutable",
        "No material scope change may be built before an approved Change Request exists",
        "Cost and time impact must be shown before customer approval",
        "Internal bug fixes, agreed-scope defects and remediation are not automatically billable scope changes",
        "preserve prior scope history"
    ]:
        if token not in inv: errors.append(f"missing invariant {token}")
if errors:
    print("LDS Change Request Scope Ledger: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Change Request Scope Ledger: PASS")
