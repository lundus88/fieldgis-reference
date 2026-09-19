#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("docs/commercial/lds-customer-disappointment-prevention")
errors=[]
for f in ["README.md","risk-register.json","customer_risk.py","test_customer_risk.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")

if (root/"risk-register.json").exists():
    d=json.loads((root/"risk-register.json").read_text())
    if d.get("schema")!="lds.customer-disappointment-prevention/1":
        errors.append("schema drift")
    ids={x.get("id") for x in d.get("risks",[])}
    for rid in ["CDP-001","CDP-002","CDP-004","CDP-008","CDP-009","CDP-010","CDP-016","CDP-017","CDP-018","CDP-019"]:
        if rid not in ids: errors.append(f"missing risk {rid}")
    rules=" ".join(d.get("mandatory_rules",[]))
    for token in ["HUMAN_ESCALATION","evidence","rebaselined","human-controlled","First response SLA","repeat already-confirmed","adoption"]:
        if token not in rules: errors.append(f"mandatory rule missing {token}")

if errors:
    print("LDS Customer Disappointment Prevention: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Customer Disappointment Prevention: PASS")
