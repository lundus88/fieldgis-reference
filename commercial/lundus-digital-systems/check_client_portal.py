#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("commercial/lundus-digital-systems")
errors=[]
for f in ["client-portal.html","client-portal-contract.json","client_portal_state.py","test_client_portal_state.py","CLIENT_PORTAL_V1.md"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"client-portal-contract.json").exists():
    d=json.loads((root/"client-portal-contract.json").read_text())
    if d.get("schema")!="lds.client-portal/1": errors.append("schema drift")
    if d.get("mode")!="READ_ONLY_COMPOSITION": errors.append("portal must be read-only composition")
    if d.get("production_activation_authorized") is not False: errors.append("production activation must remain false")
    inv=" ".join(d.get("invariants",[]))
    for x in ["cannot mark PAID","cannot mark QA passed","cannot mark UAT accepted","cannot infer Production deployment","authorized customer account/project"]:
        if x not in inv: errors.append(f"missing invariant {x}")
page=(root/"client-portal.html").read_text() if (root/"client-portal.html").exists() else ""
for x in ["Customer Control Center","Commercial","Delivery Progress","Latest verified update","Evidence before done","Request a Change — Coming Soon","UAT Approval — Coming Soon"]:
    if x not in page: errors.append(f"portal page missing {x}")
if errors:
    print("LDS Client Portal: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Client Portal: PASS")
