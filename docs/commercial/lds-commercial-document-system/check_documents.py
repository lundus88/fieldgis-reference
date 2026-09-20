#!/usr/bin/env python3
from pathlib import Path
import json,sys,re
root=Path("docs/commercial/lds-commercial-document-system")
errors=[]
for f in ["README.md","contract.json","commercial-doc.css","quotation.html","invoice.html","receipt.html"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.commercial-document-system/1": errors.append("schema drift")
    txt=" ".join(d.get("invariants",[]))
    for token in ["authoritative order/payment","tax e-Invoice","immutable","Void/correction"]:
        if token not in txt: errors.append(f"missing invariant {token}")
for f in ["quotation.html","invoice.html","receipt.html"]:
    p=root/f
    if p.exists():
        t=p.read_text()
        for token in ["LUNDUS DIGITAL SYSTEMS","commercial-doc.css"]:
            if token not in t: errors.append(f"{f} missing {token}")
if (root/"receipt.html").exists() and "PAID" not in (root/"receipt.html").read_text():
    errors.append("receipt paid marker missing")
if errors:
    print("LDS Commercial Document System: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Commercial Document System: PASS")
