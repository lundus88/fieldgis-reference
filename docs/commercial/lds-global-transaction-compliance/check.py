#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-global-transaction-compliance")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.global-transaction-compliance/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    text=" ".join(d.get("invariants",[]))
    for t in ["must not invent","does not provide tax advice","Unsupported markets","human-authorized"]:
        if t not in text: errors.append(f"missing invariant {t}")
if errors:
    print("LD Global Transaction Compliance: FAIL"); [print("-",e) for e in errors]; sys.exit(1)
print("LD Global Transaction Compliance: PASS")
