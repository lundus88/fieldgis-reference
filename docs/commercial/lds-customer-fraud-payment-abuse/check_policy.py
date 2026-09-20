#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-customer-fraud-payment-abuse")
errors=[]
for f in ["README.md","policy.json","fraud_gate.py","test_fraud_gate.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"policy.json").exists():
    d=json.loads((root/"policy.json").read_text())
    if d.get("schema")!="lds.customer-fraud-payment-abuse/1": errors.append("schema drift")
    ids={x.get("id") for x in d.get("risks",[])}
    for rid in [f"CFP-{i:03d}" for i in range(1,11)]:
        if rid not in ids: errors.append(f"missing {rid}")
    inv=" ".join(d.get("invariants",[]))
    for token in ["No funded milestone","Potential abuse signals do not prove fraud","HUMAN_ONLY","Off-channel payment"]:
        if token not in inv: errors.append(f"missing invariant {token}")
if errors:
    print("LDS Customer Fraud & Payment Abuse Protection: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Customer Fraud & Payment Abuse Protection: PASS")
