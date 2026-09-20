#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-integration-readiness")
errors=[]
for f in ["README.md","matrix.json"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"matrix.json").exists():
    d=json.loads((root/"matrix.json").read_text())
    if d.get("schema")!="lds.integration-readiness-matrix/1": errors.append("schema drift")
    if d.get("merge_authorized") is not False: errors.append("merge must remain unauthorized")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain unauthorized")
    rules=" ".join(d.get("hard_rules",[]))
    for t in ["exact-head CI green","Independent reviewer submission","base drift","Production activation authority","PR 317"]:
        if t not in rules: errors.append(f"missing hard rule {t}")
if errors:
    print("LDS Integration Readiness Matrix: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Integration Readiness Matrix: PASS")
