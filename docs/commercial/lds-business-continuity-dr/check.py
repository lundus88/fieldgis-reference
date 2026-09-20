#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-business-continuity-dr")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.business-continuity-dr/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    if d.get("automatic_restore_authorized") is not False: errors.append("automatic restore must remain false")
    text=" ".join(d.get("invariants",[]))
    for t in ["approved RPO","tested restore path","Data integrity uncertainty","explicit human authority","must not silently weaken","does not itself authorize"]:
        if t not in text: errors.append(f"missing invariant {t}")
if errors:
    print("LD Business Continuity DR: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD Business Continuity DR: PASS")
