#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("docs/commercial/lds-global-demand-engine")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file():
        errors.append(f"missing {f}")

if (root/"contract.json").exists():
    c=json.loads((root/"contract.json").read_text())
    if c.get("schema")!="lds.global-demand-engine/1":
        errors.append("schema drift")
    if c.get("principle")!="Any qualified customer. Any supported market. One digital workflow.":
        errors.append("principle drift")
    if c.get("authority",{}).get("global_paid_order")!="HOLD":
        errors.append("global paid order must remain HOLD")
    if c.get("authority",{}).get("public_global_checkout")!="HOLD":
        errors.append("public global checkout must remain HOLD")
    if c.get("authority",{}).get("production_activation")!="NOT_AUTHORIZED":
        errors.append("production must remain unauthorized")
    deps=c.get("dependencies",{})
    for key in ["pr_296_global_commerce_readiness","pr_317_integrated_customer_lifecycle"]:
        if "NOT_SATISFIED" not in deps.get(key,""):
            errors.append(f"dependency {key} must remain unsatisfied until merged")
    inv=" ".join(c.get("invariants",[]))
    for token in ["bypass lead qualification","bypass market-support evaluation","No automatic payment","Purchased or spam lists","Production and deployment authority remain HUMAN_ONLY"]:
        if token not in inv:
            errors.append(f"missing invariant {token}")

if errors:
    print("LDS Global Demand Engine: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Global Demand Engine: PASS")
