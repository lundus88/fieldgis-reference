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

if pack.get("status")!="HOLD_EXACT_PROVIDER_EVIDENCE_REQUIRED":
    errors.append("Zoho pack must remain evidence HOLD")
if pack.get("dns_mutation_authorized") is not False:
    errors.append("DNS mutation must remain unauthorized")
if domain.get("authority",{}).get("dns_mutation_authorized") is not False:
    errors.append("domain manifest DNS mutation must remain unauthorized")
if domain.get("gate_status",{}).get("OFFICIAL_CHANNELS_SELECTED")!="PASS":
    errors.append("official channels selected should be PASS")
for gate in ["ZOHO_EXACT_DNS_RECORDS_CAPTURED","EMAIL_DNS_AUTHENTICATION","OFFICIAL_COMMERCIAL_EMAIL","SUPPORT_COMPLAINT_CHANNEL","LEGAL_TRUST_READY","PUBLIC_LAUNCH"]:
    if domain.get("gate_status",{}).get(gate)!="HOLD":
        errors.append(f"{gate} must remain HOLD")

rules=" ".join(pack.get("provider_rules",[]))
for token in ["only the MX records provided","generic Zoho MX examples","one SPF TXT policy","DKIM selector","DMARC remains deferred"]:
    if token not in rules:
        errors.append(f"provider safety rule missing: {token}")

if errors:
    print("LDS Zoho Email DNS Readiness: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS Zoho Email DNS Readiness: PASS")
print("official_channels_selected=PASS")
print("exact_zoho_dns_records=HOLD")
print("dns_mutation_authorized=false")
print("legal_trust=HOLD")

# Exabytes DNS inventory evidence
ex=pack.get("exabytes_dns_state",{})
if ex.get("dns_zone_present") is not True:
    errors.append("Exabytes DNS zone must be evidenced as present")
if ex.get("dns_manager_access_verified") is not True:
    errors.append("Exabytes DNS Manager access must be evidenced")
existing=ex.get("existing_records",{})
mx=existing.get("mx",[])
if not mx or mx[0].get("rdata")!="0 lundusdigital.com":
    errors.append("existing root MX evidence drift")
if existing.get("txt_count")!=0:
    errors.append("observed TXT count drift")
draft=pack.get("change_set_draft",{})
if draft.get("status")!="DRAFT_BLOCKED_ON_ZOHO_EXACT_VALUES":
    errors.append("change-set must remain blocked on exact Zoho values")
if draft.get("dns_mutation_authorized") is not False:
    errors.append("change-set must not authorize DNS mutation")
