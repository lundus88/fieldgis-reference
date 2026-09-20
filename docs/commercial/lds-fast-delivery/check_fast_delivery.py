#!/usr/bin/env python3
from pathlib import Path
import json, sys

root = Path("docs/commercial/lds-fast-delivery")
errors = []

required = ["README.md","fast-delivery-contract.json","fast_delivery.py","test_fast_delivery.py"]
for name in required:
    if not (root/name).is_file():
        errors.append(f"missing {name}")

if (root/"fast-delivery-contract.json").exists():
    d=json.loads((root/"fast-delivery-contract.json").read_text())
    if d.get("schema")!="lds.fast-delivery-system/1":
        errors.append("unexpected schema")
    if d.get("release_authority")!="HUMAN_ONLY":
        errors.append("release authority must remain HUMAN_ONLY")
    if d.get("production_activation_authorized") is not False:
        errors.append("production activation must remain false")
    if d.get("payment_activation_authorized") is not False:
        errors.append("payment activation must remain false")
    if d.get("online_only_default") is not True:
        errors.append("online-only default must be true")
    if "final_acceptance" not in d.get("uat",{}).get("human_required",[]):
        errors.append("UAT final acceptance must require human")

q=Path("docs/commercial/templates/QUOTATION_TEMPLATE_BM.md")
if q.exists():
    qt=q.read_text()
    for token in ["{{DELIVERY_LANE}}","{{FIRST_VISIBLE_VALUE_TARGET}}","{{CUSTOMER_DEPENDENCIES}}","{{DELIVERY_STATUS_REFERENCE}}"]:
        if token not in qt:
            errors.append(f"quotation missing {token}")

a=Path("docs/commercial/templates/DELIVERY_ACCEPTANCE_TEMPLATE_BM.md")
if a.exists():
    at=a.read_text()
    for token in ["UAT evidence","Final acceptance authority","HUMAN"]:
        if token not in at:
            errors.append(f"delivery acceptance missing {token}")

if errors:
    print("LDS Fast Delivery System: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS Fast Delivery System: PASS")
