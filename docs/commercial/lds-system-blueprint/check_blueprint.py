#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-system-blueprint")
errors=[]
for f in ["README.md","contract.json","blueprint_engine.py","test_blueprint_engine.py"]:
  if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
  d=json.loads((root/"contract.json").read_text())
  if d.get("schema")!="lds.system-blueprint/1": errors.append("schema drift")
  if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
  txt=" ".join(d.get("rules",[]))
  for x in ["does not authorize BUILDING","does not create a binding price","Change Request"]:
    if x not in txt: errors.append(f"missing rule {x}")
if errors:
  print("LDS System Blueprint: FAIL")
  [print("-",e) for e in errors]
  sys.exit(1)
print("LDS System Blueprint: PASS")
