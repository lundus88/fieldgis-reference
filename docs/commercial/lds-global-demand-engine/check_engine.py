#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("docs/commercial/lds-global-demand-engine")
errors=[]
required=[
    "README.md","contract.json","engine.py","test_engine.py",
    "diagnostic.py","test_diagnostic.py","proof_engine.py","test_proof_engine.py",
    "productized_offers.json","buyer_confidence_center.json","validation_playbook.md","validation_cohort.py","test_validation_cohort.py"
]
for f in required:
    if not (root/f).is_file():
        errors.append(f"missing {f}")

if (root/"contract.json").exists():
    c=json.loads((root/"contract.json").read_text())
    if c.get("schema")!="lds.global-demand-engine/1":
        errors.append("schema drift")
    if c.get("principle")!="Any qualified customer. Any supported market. One digital workflow.":
        errors.append("principle drift")
    auth=c.get("authority",{})
    if auth.get("global_paid_order")!="HOLD":
        errors.append("global paid order must remain HOLD")
    if auth.get("public_global_checkout")!="HOLD":
        errors.append("public global checkout must remain HOLD")
    if auth.get("production_activation")!="NOT_AUTHORIZED":
        errors.append("production must remain unauthorized")
    deps=c.get("dependencies",{})
    for key in ["pr_296_global_commerce_readiness","pr_317_integrated_customer_lifecycle"]:
        if "NOT_SATISFIED" not in deps.get(key,""):
            errors.append(f"dependency {key} must remain unsatisfied until merged")
    if c.get("marketing_hook")!="Tell us the business problem. We build the digital system.":
        errors.append("marketing hook drift")
    if sorted(c.get("growth_flywheel",{}).keys())!=["capture_loop","demand_loop","expansion_loop","proof_loop","referral_loop"]:
        errors.append("growth flywheel incomplete")
    if c.get("digital_business_check",{}).get("commercial_authority") is not False:
        errors.append("digital business check must remain advisory")
    v=c.get("controlled_validation",{})\n    if v.get("scale_authority") is not False:\n        errors.append("controlled validation must not grant scale authority")\n    if v.get("production_authority")!="HUMAN_ONLY":\n        errors.append("controlled validation production authority drift")\n    p0=c.get("p0_conversion_system",{})
    if set(p0.keys())!={"trust_and_proof_engine","buyer_confidence_center","productized_offers"}:
        errors.append("P0 conversion system incomplete")
    if p0.get("productized_offers",{}).get("payment_authority") is not False:
        errors.append("productized offers must not grant payment authority")
    inv=" ".join(c.get("invariants",[]))
    tokens=[
        "bypass lead qualification","bypass market-support evaluation","No automatic payment",
        "Purchased or spam lists","Production and deployment authority remain HUMAN_ONLY",
        "Referral rewards require accepted delivery","Digital Business Check is advisory",
        "must not fabricate ROI","Proof claims must be evidence-backed",
        "fail to NEEDS_REVIEW","never grant automatic quotation or payment authority"
    ]
    for token in tokens:
        if token not in inv:
            errors.append(f"missing invariant {token}")

if (root/"productized_offers.json").exists():
    o=json.loads((root/"productized_offers.json").read_text())
    ids={x.get("id") for x in o.get("offers",[])}
    if ids!={"LD_LAUNCH","LD_AUTOMATE","LD_AI","LD_SYSTEM","LD_DISCOVERY"}:
        errors.append("offer family drift")
    if o.get("payment_authority") is not False:
        errors.append("offer catalog must not grant payment authority")

if (root/"buyer_confidence_center.json").exists():
    b=json.loads((root/"buyer_confidence_center.json").read_text())
    if b.get("answer_policy",{}).get("unknown_or_unresolved")!="NEEDS_REVIEW":
        errors.append("buyer confidence center must fail unresolved answers to NEEDS_REVIEW")

if errors:
    print("LDS Global Demand Engine: FAIL")
    for e in errors:
        print("-",e)
    sys.exit(1)
print("LDS Global Demand Engine: PASS")
