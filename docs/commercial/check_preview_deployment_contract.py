#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("docs/commercial")
plan=(root/"LDS_PREVIEW_DEPLOYMENT_PLAN.md").read_text()
contract=json.loads((root/"LDS_PREVIEW_DEPLOYMENT_CONTRACT.json").read_text())
errors=[]

for token in [
    "Status: **NON-PRODUCTION / PREVIEW V4 READY**",
    "lundus-digital-systems-preview",
    "dpl_F4rugJSSdfWMmUzb6T2ShGSRnZCJ",
    "visual QA: `PASS`",
    "workflow QA: `PASS`",
    "Production promotion: not authorised",
    "Preview readiness is evidence only"
]:
    if token not in plan:
        errors.append(f"plan missing {token}")

if contract.get("schema")!="lds.preview-deployment/1":
    errors.append("preview contract schema drift")
if contract.get("status")!="preview_v4_ready_non_production":
    errors.append("preview contract status drift")
if contract.get("deployment_authorized") is not True:
    errors.append("Preview deployment authorization evidence missing")
if contract.get("project_creation_authorized") is not True:
    errors.append("Preview project creation authorization evidence missing")
if contract.get("production_promotion_authorized") is not False:
    errors.append("Production promotion must remain false")
if contract.get("project_name")!="lundus-digital-systems-preview":
    errors.append("Preview project name drift")
if contract.get("project_id")!="prj_9areW7U50izhbz8yNrXK2r1YcJ1F":
    errors.append("Preview project id drift")
if contract.get("preview_deployment_id")!="dpl_F4rugJSSdfWMmUzb6T2ShGSRnZCJ":
    errors.append("Preview deployment id drift")
if contract.get("commercial_surface_source_sha")!="57d4fe20c89e6cffc94047e7f6f7b4da4f4f538f":
    errors.append("Preview source SHA drift")
if contract.get("target")!="preview":
    errors.append("target must remain preview")
if contract.get("preview_state")!="READY":
    errors.append("Preview state must remain READY")
if contract.get("visual_qa")!="PASS":
    errors.append("Preview visual QA must remain PASS")
if contract.get("workflow_qa")!="PASS":
    errors.append("Preview workflow QA must remain PASS")
if contract.get("production_domain") is not None:
    errors.append("production_domain must remain null")
if contract.get("production_alias_authorized") is not False:
    errors.append("Production alias authorization must remain false")
for key in [
    "customer_data_allowed",
    "live_form_submission_allowed",
    "live_checkout_allowed",
    "public_lead_intake_allowed",
    "production_secrets_allowed",
    "indexing_allowed"
]:
    if contract.get(key) is not False:
        errors.append(f"{key} must remain false")
if contract.get("root_directory")!="commercial/lundus-digital-systems":
    errors.append("root_directory drift")
if contract.get("execution_state")!="preview_deployed_and_validated":
    errors.append("Preview execution state drift")
authority=contract.get("production_authority",{})
for key in ["dns_binding","payment_activation","public_lead_intake","production_promotion","public_launch"]:
    if authority.get(key) is not False:
        errors.append(f"Production authority must remain false: {key}")

if errors:
    print("LDS preview deployment contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS preview deployment contract: PASS")
print("preview_state=READY visual_qa=PASS workflow_qa=PASS")
print("production_promotion_authorized=false public_launch=false")
