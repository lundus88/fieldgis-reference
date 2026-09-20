#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-data-governance-retention")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.data-governance-retention/1": errors.append("schema drift")
    if d.get("automatic_destructive_deletion_authorized") is not False: errors.append("auto delete must remain false")
    text=" ".join(d.get("invariants",[]))
    for token in ["approved and versioned","do not themselves authorize","Legal hold","Cross-tenant export","without retaining deleted","human-authorized"]:
        if token not in text: errors.append(f"missing invariant {token}")
if errors:
    print("LD Data Governance Retention: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD Data Governance Retention: PASS")
