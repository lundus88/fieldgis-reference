#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("vl/lom-economic-participation-p0")
required=["README.md","contract.json","engine.py","test_engine.py","shadow_pilot.py","schema.sql"]
errors=[]

for name in required:
    if not (root/name).is_file():
        errors.append(f"missing {name}")

if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text(encoding="utf-8"))
    if d.get("schema")!="lom.economic-participation.p0/1":
        errors.append("schema drift")
    if d.get("production_activation_authorized") is not False:
        errors.append("production must remain false")
    if d.get("automatic_payout_authorized") is not False:
        errors.append("automatic payout must remain false")
    if d.get("protected_main_merge_authorized") is not False:
        errors.append("protected main merge must remain false")
    inv=" ".join(d.get("invariants",[]))
    for phrase in [
        "No READY state without",
        "No PASS state without",
        "Maximum two revisions",
        "one active payable entitlement",
        "Synthetic pilot evidence",
        "HUMAN_ONLY",
    ]:
        if phrase not in inv:
            errors.append(f"missing invariant: {phrase}")

if errors:
    print("LOM Economic Participation P0: FAIL")
    for e in errors:
        print("-",e)
    sys.exit(1)

print("LOM Economic Participation P0: PASS")
