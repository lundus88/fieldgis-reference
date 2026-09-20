#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-customer-knowledge-self-service")
errors=[]
for f in ["README.md","contract.json","knowledge_center.py","test_knowledge_center.py","knowledge-center.html"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.customer-knowledge-self-service/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["Known limitations must not be hidden","Stale or unverified articles","bypass security","authorized customers","incident escalation"]:
        if t not in inv: errors.append(f"missing invariant {t}")
page=(root/"knowledge-center.html").read_text() if (root/"knowledge-center.html").exists() else ""
for t in ["Getting Started","Troubleshooting","Known Limitations","Change Requests","Handover & Exit","Safety boundary"]:
    if t not in page: errors.append(f"knowledge page missing {t}")
if errors:
    print("LDS Customer Knowledge Self Service: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Customer Knowledge Self Service: PASS")
