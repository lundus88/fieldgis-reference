#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-autonomous-operations")
errors=[]
for f in ["README.md","contract.json","capability_registry.json","engine.py","test_engine.py","check_engine.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")

if (root/"contract.json").exists():
    c=json.loads((root/"contract.json").read_text())
    if c.get("schema")!="lds.autonomous-operations/1": errors.append("schema drift")
    if c.get("operating_principle")!="Client triggers the business. LD runs the workflow. Human governs exceptions and authority gates.":
        errors.append("operating principle drift")
    if c.get("outcome_principle")!="Reliable customer outcome first. Automation is the scaling mechanism.":
        errors.append("outcome principle drift")
    if c.get("action_modes")!=["AUTO","AUTO_NOTIFY","HUMAN_GATE"]:
        errors.append("action mode drift")
    a=c.get("authority",{})
    for key in ["production_deployment","live_charging","contract_exception_approval","destructive_production_action"]:
        if a.get(key) is not False: errors.append(f"{key} must remain false")
    if c.get("no_idle_policy",{}).get("documented_blocker_required") is not True:
        errors.append("no-idle blocker rule missing")

if (root/"capability_registry.json").exists():
    r=json.loads((root/"capability_registry.json").read_text())
    ids={x.get("id") for x in r.get("capabilities",[])}
    if ids!={"LD_LAUNCH","LD_AUTOMATE","LD_AI","LD_SYSTEM","LD_DISCOVERY"}:
        errors.append("capability registry drift")
    for item in r.get("capabilities",[]):
        if item.get("default_action_mode") not in {"AUTO","AUTO_NOTIFY","HUMAN_GATE"}:
            errors.append("invalid default action mode")

if errors:
    print("LDS Autonomous Operations Layer: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Autonomous Operations Layer: PASS")
