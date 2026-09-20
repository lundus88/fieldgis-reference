#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-customer-success-referral")
errors=[]
for f in ["README.md","contract.json","customer_success.py","test_customer_success.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.customer-success-referral/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["No complaint","explicit customer permission","Referral request","unresolved satisfaction signal","materially different claims"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Customer Success Referral: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Customer Success Referral: PASS")
