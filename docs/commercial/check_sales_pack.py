#!/usr/bin/env python3
from pathlib import Path
import json, sys

root=Path("docs/commercial/templates")
files={
  "quote": root/"QUOTATION_TEMPLATE_BM.md",
  "sow": root/"STATEMENT_OF_WORK_TEMPLATE.md",
  "ack": root/"ORDER_ACKNOWLEDGEMENT_TEMPLATE_BM.md",
  "delivery": root/"DELIVERY_ACCEPTANCE_TEMPLATE_BM.md",
  "contract": root/"sales-pack-contract.json",
}
errors=[]

for k,p in files.items():
    if not p.exists():
        errors.append(f"missing {k}: {p}")

if files["quote"].exists():
    t=files["quote"].read_text()
    for token in ["Jumlah penuh","{{TOTAL_AMOUNT}}","{{VALID_UNTIL}}","variation","Redirect browser bukan bukti bayaran"]:
        if token not in t: errors.append(f"quotation missing {token}")

if files["sow"].exists():
    t=files["sow"].read_text()
    for token in ["Acceptance criteria","Di luar skop","Change control","Production deployment memerlukan human approval"]:
        if token not in t: errors.append(f"SOW missing {token}")

if files["ack"].exists():
    t=files["ack"].read_text()
    for token in ["Order reference","Status pembayaran","Status fulfilment","tidak dengan sendirinya membuktikan pembayaran"]:
        if token not in t: errors.append(f"ack missing {token}")

if files["delivery"].exists():
    t=files["delivery"].read_text()
    for token in ["Delivery evidence","Receipt reference","payment = paid","fulfilment = fulfilled","human close approval"]:
        if token not in t: errors.append(f"delivery missing {token}")

if files["contract"].exists():
    data=json.loads(files["contract"].read_text())
    if data.get("schema")!="lds.sales-pack/1": errors.append("contract schema drift")
    if data.get("status")!="rc": errors.append("sales pack must remain RC until business/licence gates pass")
    required=set(data.get("required_before_customer_issue",[]))
    for key in ["verified_business_particulars","licence_ready","effective_policy_dates","official_support_channel"]:
        if key not in required: errors.append(f"contract missing release dependency {key}")

if errors:
    print("Commercial sales pack contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("Commercial sales pack contract: PASS")
