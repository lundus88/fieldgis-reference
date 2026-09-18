#!/usr/bin/env python3
from pathlib import Path
import json, sys

root=Path("docs/commercial")
files={
  "tester":root/"LDS_CONTROLLED_TESTER_PACK.md",
  "launch":root/"LDS_LAUNCH_DAY_OPERATOR_CHECKLIST.md",
  "rollback":root/"LDS_ROLLBACK_DRILL.md",
  "contract":root/"LDS_CONTROLLED_LAUNCH_OPERATIONS.json",
}
errors=[]
for k,p in files.items():
    if not p.exists(): errors.append(f"missing {k}: {p}")

if files["tester"].exists():
    t=files["tester"].read_text()
    for x in ["5–10 invited testers","No live payment.","no open P0 issues","at least 5 invited testers"]:
        if x not in t: errors.append(f"tester pack missing {x}")

if files["launch"].exists():
    t=files["launch"].read_text()
    for x in ["LICENCE_READY = PASS","LEGAL_TRUST_READY = PASS","If any item is HOLD, stop.","A browser redirect is never payment evidence."]:
        if x not in t: errors.append(f"launch checklist missing {x}")

if files["rollback"].exists():
    t=files["rollback"].read_text()
    for x in ["Disable new checkout.","Do not fulfil.","PUBLIC_LEAD_INTAKE_ENABLED=false","Disable public payment immediately."]:
        if x not in t: errors.append(f"rollback drill missing {x}")

if files["contract"].exists():
    c=json.loads(files["contract"].read_text())
    if c.get("schema")!="lds.controlled-launch-operations/1": errors.append("contract schema drift")
    if c.get("public_launch_authorized") is not False: errors.append("public launch must remain false")
    if c.get("payment_activation_authorized") is not False: errors.append("payment activation must remain false")
    if c.get("tester_target_min")!=5 or c.get("tester_target_max")!=10: errors.append("tester cohort drift")

if errors:
    print("Controlled launch operations contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("Controlled launch operations contract: PASS")
print("public_launch_authorized=false payment_activation_authorized=false")
