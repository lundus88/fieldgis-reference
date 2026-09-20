#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-subscription-entitlement")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.subscription-entitlement/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    text=" ".join(d.get("invariants",[]))
    for t in ["approved plan","outside this engine","must not automatically delete","auditable state transitions","separately authorized"]:
        if t not in text: errors.append(f"missing invariant {t}")
if errors:
    print("LD Subscription Entitlement: FAIL"); [print("-",e) for e in errors]; sys.exit(1)
print("LD Subscription Entitlement: PASS")
