#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-executive-commercial-mission-control")
errors=[]
for f in ["README.md","contract.json","executive_commercial.py","test_executive_commercial.py","dashboard.html"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    d=json.loads((root/"contract.json").read_text())
    if d.get("schema")!="lds.executive-commercial-mission-control/1": errors.append("schema drift")
    if d.get("mode")!="READ_ONLY_EXECUTIVE_COMPOSITION": errors.append("wrong mode")
    if d.get("production_activation_authorized") is not False: errors.append("production must remain false")
    inv=" ".join(d.get("invariants",[]))
    for t in ["second project or commercial source of truth","authoritative paid-order evidence","freshness and evidence completeness","absence of complaints","cannot send customer outreach"]:
        if t not in inv: errors.append(f"missing invariant {t}")
page=(root/"dashboard.html").read_text() if (root/"dashboard.html").exists() else ""
for t in ["Pipeline","Revenue","Margin","Capacity","Customer Health","Recurring Revenue","Risk & Exceptions","Authority boundary"]:
    if t not in page: errors.append(f"dashboard missing {t}")
if errors:
    print("LDS Executive Commercial Mission Control: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Executive Commercial Mission Control: PASS")
