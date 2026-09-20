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

if errors:
    print("LDS Unified Commercial Control Plane: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Unified Commercial Control Plane: PASS")
