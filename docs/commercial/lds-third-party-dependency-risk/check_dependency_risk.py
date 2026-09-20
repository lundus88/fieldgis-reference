#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-third-party-dependency-risk")
errors=[]
for f in ["README.md","contract.json","dependency_risk.py","test_dependency_risk.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.third-party-dependency-risk/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["affected customer projects","verified fallback","must not auto-switch provider","Customer notification","must never be stored"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Third Party Dependency Risk: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Third Party Dependency Risk: PASS")
