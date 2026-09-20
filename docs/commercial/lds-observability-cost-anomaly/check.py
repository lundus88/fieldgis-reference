#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-observability-cost-anomaly")
errors=[]
for f in ["README.md","contract.json","engine.py","test_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.observability-cost-anomaly/1": errors.append("schema drift")
    if d.get("automatic_shutdown_authorized") is not False: errors.append("auto shutdown must remain false")
    text=" ".join(d.get("invariants",[]))
    for token in ["current evidence","Cross-tenant","confirmed root cause","not authorized","auditable policy","does not itself authorize"]:
        if token not in text: errors.append(f"missing invariant {token}")
if errors:
    print("LD Observability Cost Anomaly: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LD Observability Cost Anomaly: PASS")
