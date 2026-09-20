#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-smart-client-discovery")
errors=[]
required=["README.md","contract.json","engine.py","test_engine.py","check_engine.py"]
for f in required:
    if not (root/f).is_file():
        errors.append(f"missing {f}")
if (root/"contract.json").exists():
    c=json.loads((root/"contract.json").read_text())
    if c.get("schema")!="lds.smart-client-discovery/1":
        errors.append("schema drift")
    if c.get("principle")!="Ask only what changes the solution.":
        errors.append("principle drift")
    a=c.get("authority",{})
    for key in ["authoritative_quotation","contract_approval","payment","delivery_date_promise","feasibility_guarantee","production_activation"]:
        if a.get(key) is not False:
            errors.append(f"{key} must remain false")
    target=c.get("primary_question_target",{})
    if target.get("min")!=5 or target.get("max")!=8:
        errors.append("primary question target drift")
    privacy=c.get("privacy",{})
    if "passwords" not in privacy.get("prohibited_default_requests",[]):
        errors.append("password privacy guard missing")
    if privacy.get("sensitive_integration_policy")!="ASK_CLASSIFICATION_NOT_SECRET":
        errors.append("sensitive integration policy drift")
if errors:
    print("LDS Smart Client Discovery: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Smart Client Discovery: PASS")
