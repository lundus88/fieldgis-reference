#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path("docs/commercial/lds-integrated-customer-lifecycle-gate")
errors=[]
for f in ["README.md","contract.json","state_graph.json","lifecycle_gate.py","test_lifecycle_gate.py"]:
    if not (root/f).is_file(): errors.append(f"missing {f}")

if (root/"contract.json").exists():
    c=json.loads((root/"contract.json").read_text())
    if c.get("schema")!="lds.unified-commercial-control-plane/1": errors.append("contract schema drift")
    if c.get("global_transaction_principle")!="Any qualified customer. Any supported market. One digital workflow.":
        errors.append("global transaction principle drift")
    if c.get("production_activation_authorized") is not False: errors.append("production activation must remain false")
    if c.get("live_charging_authorized") is not False: errors.append("live charging must remain false")
    inv=" ".join(c.get("invariants",[]))
    for token in [
      "must not create a second source of truth",
      "allowed state-graph edge",
      "never substitutes for required transition evidence",
      "explicit and auditable",
      "Cross-organization authority is denied",
      "idempotency keys",
      "payment redirect",
      "separate HUMAN_ONLY authorities"
    ]:
        if token not in inv: errors.append(f"missing invariant {token}")

if (root/"state_graph.json").exists():
    g=json.loads((root/"state_graph.json").read_text())
    if g.get("schema")!="lds.unified-commercial-control-plane.state-graph/1": errors.append("state graph schema drift")
    states=set(g.get("states",[]))
    for t in g.get("transitions",[]):
        if t.get("from") not in states or t.get("to") not in states:
            errors.append("transition references unknown state")
        if not isinstance(t.get("evidence"),list) or not isinstance(t.get("dependencies"),list):
            errors.append("transition contract shape invalid")
        if "any_evidence" in t and not isinstance(t.get("any_evidence"),list):
            errors.append("any_evidence contract shape invalid")
    kickoff=[t for t in g.get("transitions",[]) if t.get("from")=="PAYMENT_RECONCILED" and t.get("to")=="KICKOFF_APPROVED"]
    if len(kickoff)!=1:
        errors.append("kickoff transition missing or duplicated")
    else:
        k=kickoff[0]
        if set(k.get("any_evidence",[]))!={"autonomous_kickoff_eligibility","human_kickoff_approval"}:
            errors.append("autonomous/human kickoff evidence policy drift")
        if k.get("human_authority") is not False:
            errors.append("standard kickoff edge must allow autonomous eligibility receipt")
        if "autonomous_operations" not in k.get("dependencies",[]):
            errors.append("autonomous operations dependency missing")

if errors:
    print("LDS Unified Commercial Control Plane: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Unified Commercial Control Plane: PASS")
