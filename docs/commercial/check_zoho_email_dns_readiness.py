#!/usr/bin/env python3
from pathlib import Path
import json,sys

docs=Path("docs/commercial")
errors=[]

domain=json.loads((docs/"LDS_DOMAIN_EMAIL_READINESS.json").read_text())
pack=json.loads((docs/"LDS_ZOHO_EMAIL_DNS_READINESS.json").read_text())

if domain.get("schema")!="lds.domain-email-readiness/1":
    errors.append("domain/email schema drift")
if pack.get("schema")!="lds.zoho-email-dns-readiness/1":
    errors.append("Zoho readiness schema drift")

channels=domain.get("email",{}).get("official_channel_selection",{})
expected={
    "primary_commercial_email":"hello@lundusdigital.com",
    "support_complaint_email":"support@lundusdigital.com",
    "billing_email":"billing@lundusdigital.com"
}
for key,value in expected.items():
    item=channels.get(key,{})
    if item.get("value")!=value:
        errors.append(f"channel drift: {key}")
    if item.get("status")!="SELECTED_NOT_VERIFIED":
        errors.append(f"channel must remain unverified: {key}")

records=pack.get("exact_record_capture",{})
for key in ["domain_verification","mx","spf","dkim"]:
    if key not in records:
        errors.append(f"missing exact record capture section: {key}")

verify=records.get("domain_verification",{})
if verify.get("record_type")!="TXT":
    errors.append("Zoho verification type drift")
if verify.get("host")!="@":
    errors.append("Zoho verification host drift")
if verify.get("value")!="zoho-verification=zb36894990.zmverify.zoho.com":
    errors.append("Zoho verification value drift")
if verify.get("status")!="CAPTURED_NOT_APPLIED":
    errors.append("Zoho verification must remain captured-not-applied")

if pack.get("status")!="HOLD_EXACT_PROVIDER_EVIDENCE_REQUIRED":
    errors.append("Zoho pack must remain evidence HOLD")
if pack.get("dns_mutation_authorized") is not False:
    errors.append("DNS mutation must remain unauthorized")
if domain.get("authority",{}).get("dns_mutation_authorized") is not False:
    errors.append("domain manifest DNS mutation must remain unauthorized")

gates=domain.get("gate_status",{})
for gate in ["OFFICIAL_CHANNELS_SELECTED","DNS_ZONE_PRESENT","EXISTING_DNS_INVENTORY_CAPTURED","ZOHO_DOMAIN_VERIFICATION_RECORD_CAPTURED"]:
    if gates.get(gate)!="PASS":
        errors.append(f"{gate} must be PASS")
for gate in ["ZOHO_EXACT_DNS_RECORDS_CAPTURED","EMAIL_DNS_AUTHENTICATION","OFFICIAL_COMMERCIAL_EMAIL","SUPPORT_COMPLAINT_CHANNEL","LEGAL_TRUST_READY","PUBLIC_LAUNCH"]:
    if gates.get(gate)!="HOLD":
        errors.append(f"{gate} must remain HOLD")

ex=pack.get("exabytes_dns_state",{})
if ex.get("dns_zone_present") is not True:
    errors.append("Exabytes DNS zone must be evidenced as present")
existing=ex.get("existing_records",{})
mx=existing.get("mx",[])
if len(mx)!=1 or mx[0].get("rdata")!="0 lundusdigital.com":
    errors.append("existing root MX evidence drift")
if existing.get("txt_count")!=0:
    errors.append("observed TXT count drift")

draft=pack.get("change_set_draft",{})
if draft.get("status")!="PARTIAL_EXACT_VALUES_CAPTURED_MX_SPF_DKIM_PENDING":
    errors.append("change-set status drift")
if draft.get("dns_mutation_authorized") is not False:
    errors.append("change-set must not authorize DNS mutation")
ready=draft.get("add_ready_for_human_application_review",[])
if "TXT @ = zoho-verification=zb36894990.zmverify.zoho.com" not in ready:
    errors.append("exact Zoho verification TXT missing from review-ready change set")

change=(docs/"LDS_EMAIL_DNS_CHANGESET_DRAFT.md").read_text()
for token in [
    "zoho-verification=zb36894990.zmverify.zoho.com",
    "Do not change A/CNAME/NS/MX yet.",
    "Verify TXT Record",
    "DNS mutation authorized by repository: **NO**"
]:
    if token not in change:
        errors.append(f"DNS change-set guard missing: {token}")

if errors:
    print("LDS Zoho Email DNS Readiness: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS Zoho Email DNS Readiness: PASS")
print("zoho_domain_verification_record=CAPTURED_NOT_APPLIED")
print("mx_spf_dkim=HOLD")
print("dns_mutation_authorized=false")
