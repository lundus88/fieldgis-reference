#!/usr/bin/env python3
from pathlib import Path
import json
import sys

errors=[]
docs=Path("docs/commercial")
root=Path("commercial/lundus-digital-systems")

manifest=json.loads((docs/"LDS_PRELAUNCH_PARALLEL_HARDENING.json").read_text())
if manifest.get("schema")!="lds.prelaunch-parallel-hardening/1":
    errors.append("prelaunch hardening schema drift")
if manifest.get("mode")!="NON_PRODUCTION_PRELAUNCH":
    errors.append("hardening mode must remain NON_PRODUCTION_PRELAUNCH")

for key in [
    "production_activation_authorized","live_payment_authorized","dns_mutation_authorized",
    "live_lead_intake_authorized","public_launch_authorized","external_secret_capture_in_repository"
]:
    if manifest.get("authority",{}).get(key) is not False:
        errors.append(f"authority must remain false: {key}")

if manifest.get("legal_trust",{}).get("remaining_blockers")!=["LD_DEDICATED_BUSINESS_PHONE_VERIFIED"]:
    errors.append("Legal & Trust blocker set drift")

config=manifest.get("tracks",{}).get("configuration_preflight",{})
required_later=set(config.get("requires_later_production_evidence",[]))
for token in [
    "LUNDUS_COMMERCIAL_ORIGIN","Turnstile site key","Turnstile secret","Turnstile hostname/action",
    "WAF or edge rate-limit rule","LundusLead owner UUID","Billplz Production API secret",
    "Billplz Collection ID","Billplz X-signature secret","Resend Production API key",
    "Resend Production sender","Resend Production webhook secret"
]:
    if token not in required_later:
        errors.append(f"missing Production preflight evidence requirement: {token}")

lead=json.loads((root/"lead-intake-contract.json").read_text())
if lead.get("client_to_lunduslead_direct_write") is not False:
    errors.append("browser direct write to LundusLead must remain false")
for action in ["auto_quotation","auto_pricing","auto_payment","auto_sale","direct_browser_write_to_internal_crm"]:
    if action not in lead.get("forbidden_actions",[]):
        errors.append(f"lead contract missing forbidden action: {action}")

domain=json.loads((docs/"LDS_DOMAIN_EMAIL_READINESS.json").read_text())
security=domain.get("security",{})
for key,value in {
    "registrar_2fa":"NOT_EVIDENCED",
    "domain_transfer_lock":"NOT_EVIDENCED",
    "dnssec":"NOT_EVALUATED",
}.items():
    if security.get(key)!=value:
        errors.append(f"domain security evidence state drift: {key}")
if security.get("auto_renew")!="VERIFIED_ENABLED":
    errors.append("domain auto-renew evidence drift")

gate=(docs/"LDS_FINAL_COMMERCIAL_ACTIVATION_GATE.md").read_text()
stale="Verified SSM phone/address evidence is retained only as registration evidence and is not selected for LD's public identity."
if stale in gate:
    errors.append("stale public-address wording remains in final activation gate")
if "explicitly approved for public commercial display on 21 September 2026" not in gate:
    errors.append("approved SSM address publication wording missing")

payment=(docs/"PAYMENT_PRODUCTION_READINESS_RC.md").read_text()
for token in [
    "Production deployment: NOT AUTHORISED",
    "Live billing activation: BLOCKED",
    "Browser submits only an approved `offer_key`",
    "Billplz callback is HMAC-verified",
    "Duplicate callbacks are idempotent",
    "PAYMENT_PRODUCTION_READY = HOLD",
]:
    if token not in payment:
        errors.append(f"payment readiness guard missing: {token}")

hygiene=manifest.get("tracks",{}).get("open_pr_hygiene",{})
if hygiene.get("close_authorized") is not False or hygiene.get("merge_authorized") is not False:
    errors.append("open PR hygiene must not authorize close/merge")
for item in hygiene.get("superseded_candidates",[]):
    if item.get("pr") in [199,200,201,202,203,204] and item.get("ahead_by")!=0:
        errors.append(f"superseded candidate unexpectedly has unique commits: PR #{item.get('pr')}")
review={x.get("pr"):x for x in hygiene.get("review_required",[])}
if review.get(218,{}).get("classification")!="DIVERGED_UNIQUE_COMMITS_REVIEW_REQUIRED":
    errors.append("PR #218 review-required classification missing")

if errors:
    print("LDS Prelaunch Parallel Hardening: FAIL")
    for e in errors:
        print("-",e)
    sys.exit(1)

print("LDS Prelaunch Parallel Hardening: PASS")
print("mode=NON_PRODUCTION_PRELAUNCH")
print("legal_trust=HOLD_PHONE_ONLY")
print("production_activation=HOLD")
print("live_payment=HOLD")
print("live_lead_intake=HOLD")
print("dns_mutation=HOLD")
print("public_launch=HOLD")
