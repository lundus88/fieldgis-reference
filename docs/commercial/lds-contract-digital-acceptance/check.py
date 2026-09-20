#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-contract-digital-acceptance")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.contract-digital-acceptance/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    text=" ".join(d.get("invariants",[]))
    for t in ["exact immutable","explicit customer acceptance","must not be inferred","new acceptance record","does not provide legal advice"]:
        if t not in text: errors.append(f"missing invariant {t}")
if errors:
    print("LD Contract Digital Acceptance: FAIL"); [print("-",e) for e in errors]; sys.exit(1)
print("LD Contract Digital Acceptance: PASS")
