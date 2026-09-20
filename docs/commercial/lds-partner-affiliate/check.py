#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-partner-affiliate")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.partner-affiliate/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    if d.get("automatic_partner_payout_authorized") is not False: errors.append("automatic payout must remain false")
    text=" ".join(d.get("invariants",[]))
    for t in ["Only approved partners","Self-referral","approved and versioned","must not become final payable","never automatic","must not bypass"]:
        if t not in text: errors.append(f"missing invariant {t}")
if errors:
    print("LD Partner Affiliate: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD Partner Affiliate: PASS")
