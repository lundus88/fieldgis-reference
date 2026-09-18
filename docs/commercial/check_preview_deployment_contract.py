#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("docs/commercial")
plan=(root/"LDS_PREVIEW_DEPLOYMENT_PLAN.md").read_text()
contract=json.loads((root/"LDS_PREVIEW_DEPLOYMENT_CONTRACT.json").read_text())
errors=[]

for token in [
    "Status: NON-PRODUCTION",
    "Approval received on 2026-09-19",
    "deployment target: preview only",
    "Production payment secrets: absent",
    "customer data: prohibited",
    "real customer charging: prohibited",
    "AUTHORIZED_PENDING_SAFE_MUTATION_PATH",
    "Do not promote to Production."
]:
    if token not in plan:
        errors.append(f"plan missing {token}")

if contract.get("schema")!="lds.preview-deployment/1":
    errors.append("preview contract schema drift")
if contract.get("status")!="authorized_pending_safe_mutation_path":
    errors.append("preview status must reflect human approval plus safe-tooling hold")
if contract.get("deployment_authorized") is not True:
    errors.append("deployment_authorized must be true after human approval")
if contract.get("project_creation_authorized") is not True:
    errors.append("project_creation_authorized must be true after human approval")
if contract.get("production_promotion_authorized") is not False:
    errors.append("production promotion must remain false")
for key in ["customer_data_allowed","live_form_submission_allowed","live_checkout_allowed","production_secrets_allowed","indexing_allowed"]:
    if contract.get(key) is not False:
        errors.append(f"{key} must remain false")
if contract.get("target")!="preview":
    errors.append("target must remain preview")
if contract.get("production_domain") is not None:
    errors.append("production_domain must remain null")
if contract.get("root_directory")!="commercial/lundus-digital-systems":
    errors.append("root_directory drift")
if contract.get("execution_state")!="blocked_by_tool_scope_ambiguity":
    errors.append("execution_state must remain blocked until a safe project-scoped mutation path exists")

if errors:
    print("LDS preview deployment contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS preview deployment contract: PASS")
print("project_creation_authorized=true deployment_authorized=true production_promotion_authorized=false")
print("execution_state=blocked_by_tool_scope_ambiguity")
