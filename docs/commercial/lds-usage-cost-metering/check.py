#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-usage-cost-metering")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.usage-cost-metering/1": errors.append("schema drift")
    if d.get("automatic_customer_charge_authorized") is not False: errors.append("auto charge must remain false")
    text=" ".join(d.get("invariants",[]))
    for token in ["evidence-backed","Cross-tenant","not automatically a customer price","must not produce a billable","approved quotation subscription","No automatic customer charging"]:
        if token not in text: errors.append(f"missing invariant {token}")
if errors:
    print("LD Usage Cost Metering: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD Usage Cost Metering: PASS")
