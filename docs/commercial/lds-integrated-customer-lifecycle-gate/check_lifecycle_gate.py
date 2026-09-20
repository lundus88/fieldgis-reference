#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-integrated-customer-lifecycle-gate")
errors=[]
for f in ["README.md","contract.json","lifecycle_gate.py","test_lifecycle_gate.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"contract.json").exists():
    c=json.loads((root/"contract.json").read_text())
    if c.get("schema")!="lds.integrated-customer-lifecycle-gate/1": errors.append("contract schema drift")
    if c.get("global_transaction_principle")!="Any qualified customer. Any supported market. One digital workflow.":
        errors.append("global transaction principle drift")
    if c.get("north_star")!="From any legitimate lead in the world to a completed paid digital service with minimal human friction.":
        errors.append("north star drift")
    expected=["VISITOR","QUALIFIED_LEAD","QUOTATION","PAYMENT","DELIVERY","ACCEPTANCE","REPEAT_OR_REFERRAL"]
    if c.get("commercial_kpi_chain")!=expected: errors.append("commercial KPI chain drift")
    inv=" ".join(c.get("invariants",[]))
    for token in ["must never authorize a hard lifecycle transition","Visitor state carries no project or payment authority","must not bypass market support","Repeat or referral status requires completed delivery"]:
        if token not in inv: errors.append(f"missing invariant {token}")
    if c.get("production_activation_authorized") is not False: errors.append("production activation must remain false")
if errors:
    print("LDS Integrated Customer Lifecycle Gate: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Integrated Customer Lifecycle Gate: PASS")
