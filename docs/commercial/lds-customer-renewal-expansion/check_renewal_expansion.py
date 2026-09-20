#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-customer-renewal-expansion")
errors=[]
for f in ["README.md","contract.json","renewal_expansion.py","test_renewal_expansion.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.customer-renewal-expansion/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["customer-specific evidence","RETENTION_FOLLOW_UP","No complaint","never automatic outreach","cannot auto-contact"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Customer Renewal Expansion: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Customer Renewal Expansion: PASS")
