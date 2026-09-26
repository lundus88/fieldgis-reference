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
    "CURRENT_PREVIEW_REFRESHED_STATIC_QA_PASS_VISUAL_RERUN_HOLD",
    "dpl_EtpmqbwrL8G3rdRMgfxjTpBY9yhK",
    "Do not promote to Production."
]:
    if token not in plan:
        errors.append(f"plan missing {token}")

if contract.get("schema")!="lds.preview-deployment/1":
    errors.append("preview contract schema drift")
if contract.get("status")!="deployed_current_static_verified_visual_rerun_hold":
    errors.append("preview status must reflect refreshed non-Production deployment plus visual HOLD")
if contract.get("deployment_authorized") is not True:
    errors.append("deployment_authorized must remain true after human approval")
if contract.get("project_creation_authorized") is not True:
    errors.append("project_creation_authorized must remain true after human approval")
if contract.get("production_promotion_authorized") is not False:
    errors.append("production promotion must remain false")
for key in ["customer_data_allowed","live_form_submission_allowed","live_checkout_allowed","production_secrets_allowed","indexing_allowed"]:
    if contract.get(key) is not False:
        errors.append(f"{key} must remain false")
if contract.get("target")!="preview":
    errors.append("contract target classification must remain preview")
if contract.get("production_domain") is not None:
    errors.append("production_domain must remain null")
if contract.get("root_directory")!="commercial/lundus-digital-systems":
    errors.append("root_directory drift")
if contract.get("execution_state")!="current_preview_refresh_complete":
    errors.append("execution_state must record completed project-scoped Preview refresh")

current=contract.get("current_preview",{})
if current.get("project_id")!="prj_9areW7U50izhbz8yNrXK2r1YcJ1F":
    errors.append("current Preview project id drift")
if current.get("deployment_id")!="dpl_EtpmqbwrL8G3rdRMgfxjTpBY9yhK":
    errors.append("current Preview deployment id drift")
if current.get("source_sha")!="42b16dfb2a27e09b41cdf1ebbbd2c0dff02adb54":
    errors.append("current Preview source SHA drift")
if current.get("state")!="READY":
    errors.append("current Preview state must remain READY")
if current.get("api_target") is not None:
    errors.append("current Preview API target must remain non-Production/null")
if current.get("aliases") != []:
    errors.append("current Preview must not have aliases")
if current.get("environment_keys") != []:
    errors.append("current Preview project must remain free of configured environment keys")
if current.get("static_surface_qa")!="PASS" or current.get("responsive_structure_qa")!="PASS":
    errors.append("current Preview static/responsive QA must remain PASS")
if current.get("current_visual_browser_qa")!="HOLD":
    errors.append("current rendered visual QA must remain HOLD until explicitly reverified")

preflight=contract.get("preflight_evidence",{})
if preflight.get("connected_vercel_read_access") is not True:
    errors.append("connected Vercel read access evidence missing")
if preflight.get("explicit_project_scoped_rest_deployment") is not True:
    errors.append("explicit project-scoped REST deployment evidence missing")
if preflight.get("production_environment_guard")!="PASS_EMPTY_ENV":
    errors.append("Production environment guard evidence missing")
if preflight.get("vercel_cli_installed") is not False:
    errors.append("local Vercel CLI evidence drift")
if preflight.get("ephemeral_npx_auth_verified") is not False:
    errors.append("ephemeral CLI auth evidence drift")

if errors:
    print("LDS preview deployment contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS preview deployment contract: PASS")
print("project_scope=PASS current_preview=READY static_qa=PASS visual_qa=HOLD")
print("production_promotion_authorized=false")
