#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-customer-onboarding-kickoff")
errors=[]
for f in ["README.md","contract.json","kickoff_readiness.py","test_kickoff_readiness.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.customer-onboarding-kickoff/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain unauthorized")
    inv=" ".join(d.get("invariants",[]))
    for t in ["Payment or funded milestone alone","CLIENT_ACTION_REQUIRED","schedule or ETA rebaseline","Credentials and secrets","Customer owner and LD owner"]:
        if t not in inv: errors.append(f"missing invariant {t}")
if errors:
    print("LDS Customer Onboarding Kickoff: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Customer Onboarding Kickoff: PASS")
