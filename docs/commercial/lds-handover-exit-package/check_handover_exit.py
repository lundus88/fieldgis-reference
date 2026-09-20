#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-handover-exit-package")
errors=[]
for f in ["README.md","contract.json","handover_exit.py","test_handover_exit.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.handover-exit-package/1": errors.append("schema drift")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain unauthorized")
    inv=" ".join(d.get("invariants",[]))
    for token in [
      "Ownership and licensing terms",
      "must never be transmitted in plaintext",
      "Data export or portability evidence",
      "revoked or reduced",
      "Customer acceptance"
    ]:
      if token not in inv: errors.append(f"missing invariant {token}")
if errors:
    print("LDS Handover Exit Package: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Handover Exit Package: PASS")
