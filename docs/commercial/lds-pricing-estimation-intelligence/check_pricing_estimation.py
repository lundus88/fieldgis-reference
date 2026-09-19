#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-pricing-estimation-intelligence")
errors=[]
for f in ["README.md","contract.json","pricing_estimation.py","test_pricing_estimation.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.pricing-estimation-intelligence/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["Factory Credit","internal decision support only","separate human commercial approval","Insufficient historical evidence","Approved scope snapshot","must not silently increase customer price"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Pricing Estimation Intelligence: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Pricing Estimation Intelligence: PASS")
