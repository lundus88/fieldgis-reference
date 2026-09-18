#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("docs/commercial")
plan=(root/"LDS_PREVIEW_DEPLOYMENT_PLAN.md").read_text()
contract=json.loads((root/"LDS_PREVIEW_DEPLOYMENT_CONTRACT.json").read_text())
errors=[]

for token in [
    "Status: NON-PRODUCTION",
    "deployment target: preview only",
    "Production payment secrets: absent",
    "customer data: prohibited",
    "real customer charging: prohibited",
    "Do not promote to Production.",
    "does not authorize creating the Vercel project or deploying it"
]:
    if token not in plan:
        errors.append(f"plan missing {token}")

if contract.get("schema")!="lds.preview-deployment/1":
    errors.append("preview contract schema drift")
for key in ["deployment_authorized","project_creation_authorized","production_promotion_authorized","customer_data_allowed","live_form_submission_allowed","live_checkout_allowed","production_secrets_allowed","indexing_allowed"]:
    if contract.get(key) is not False:
        errors.append(f"{key} must remain false")
if contract.get("target")!="preview":
    errors.append("target must remain preview")
if contract.get("production_domain") is not None:
    errors.append("production_domain must remain null")
if contract.get("root_directory")!="commercial/lundus-digital-systems":
    errors.append("root_directory drift")

if errors:
    print("LDS preview deployment contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS preview deployment contract: PASS")
print("deployment_authorized=false project_creation_authorized=false target=preview")
