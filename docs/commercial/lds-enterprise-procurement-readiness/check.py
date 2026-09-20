#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-enterprise-procurement-readiness")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.enterprise-procurement-readiness/1": errors.append("schema drift")
    if d.get("automatic_contractual_commitment_authorized") is not False: errors.append("auto commitment must remain false")
    text=" ".join(d.get("invariants",[]))
    for token in ["current verifiable evidence","UNKNOWN or NEED_EVIDENCE","must not be asserted","separate human","does not itself create","does not authorize"]:
        if token not in text: errors.append(f"missing invariant {token}")
if errors:
    print("LD Enterprise Procurement Readiness: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD Enterprise Procurement Readiness: PASS")
