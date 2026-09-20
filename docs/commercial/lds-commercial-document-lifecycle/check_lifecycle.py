#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-commercial-document-lifecycle")
errors=[]
for f in ["README.md","contract.json","lifecycle.py","test_lifecycle.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.automated-commercial-document-lifecycle/1": errors.append("schema drift")
    inv=" ".join(d.get("invariants",[]))
    for token in ["human-approved","verified provider/backend","Receipt may be issued","human-controlled","original document references","tax e-Invoice"]:
        if token not in inv: errors.append(f"missing invariant {token}")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain unauthorized")
if errors:
    print("LDS Automated Commercial Document Lifecycle: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Automated Commercial Document Lifecycle: PASS")
