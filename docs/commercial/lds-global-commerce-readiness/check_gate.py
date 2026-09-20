#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-global-commerce-readiness")
errors=[]
for f in ["README.md","policy.json","country-support-matrix.json","gate.py","test_gate.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")
if (root/"policy.json").exists():
    p=json.loads((root/"policy.json").read_text())
    if p.get("schema")!="lds.global-commerce-readiness/1": errors.append("policy schema drift")
    if p.get("global_transaction_principle")!="Any qualified customer. Any supported market. One digital workflow.":
        errors.append("global transaction principle drift")
    if p.get("north_star")!="From any legitimate lead in the world to a completed paid digital service with minimal human friction.":
        errors.append("north star drift")
    expected=["VISITOR","QUALIFIED_LEAD","QUOTATION","PAYMENT","DELIVERY","ACCEPTANCE","REPEAT_OR_REFERRAL"]
    if p.get("commercial_kpi_chain")!=expected: errors.append("commercial KPI chain drift")
    inv=" ".join(p.get("invariants",[]))
    for token in ["Unknown or stale","human approval","separate from paid-order authority","No country may inherit","must not override market support","must not authorize a hard-state transition"]:
        if token not in inv: errors.append(f"missing invariant {token}")
if (root/"country-support-matrix.json").exists():
    m=json.loads((root/"country-support-matrix.json").read_text())
    if m.get("status")!="HOLD_NO_COUNTRY_ACTIVATED": errors.append("country matrix must start HOLD")
    if m.get("countries") not in ({},None): errors.append("v1 must not pre-approve countries")
if errors:
    print("LDS Global Commerce Readiness: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Global Commerce Readiness: PASS")
