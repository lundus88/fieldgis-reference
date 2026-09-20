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

verify=pack.get("exact_record_capture",{}).get("domain_verification",{})
if verify.get("record_type")!="TXT":
    errors.append("Zoho verification type drift")
if verify.get("host")!="@":
    errors.append("Zoho verification host drift")
if verify.get("value")!="zoho-verification=zb36894990.zmverify.zoho.com":
    errors.append("Zoho verification value drift")
if verify.get("status")!="APPLIED_PENDING_ZOHO_VERIFICATION":
    errors.append("Zoho verification must be applied-pending-provider-verification")
if verify.get("applied_ttl")!=14440:
    errors.append("applied TXT TTL evidence drift")

if pack.get("status")!="HOLD_EXACT_PROVIDER_EVIDENCE_REQUIRED":
    errors.append("overall Zoho pack must remain evidence HOLD")
if pack.get("dns_mutation_authorized") is not False:
    errors.append("general DNS mutation must remain unauthorized")
if domain.get("authority",{}).get("dns_mutation_authorized") is not False:
    errors.append("domain manifest general DNS mutation must remain unauthorized")

gates=domain.get("gate_status",{})
for gate in [
    "OFFICIAL_CHANNELS_SELECTED","DNS_ZONE_PRESENT","EXISTING_DNS_INVENTORY_CAPTURED",
    "ZOHO_DOMAIN_VERIFICATION_RECORD_CAPTURED","ZOHO_DOMAIN_VERIFICATION_DNS_APPLIED"
]:
    if gates.get(gate)!="PASS":
        errors.append(f"{gate} must be PASS")
for gate in [
    "ZOHO_DOMAIN_OWNERSHIP_VERIFIED","ZOHO_EXACT_DNS_RECORDS_CAPTURED",
    "EMAIL_DNS_AUTHENTICATION","OFFICIAL_COMMERCIAL_EMAIL",
    "SUPPORT_COMPLAINT_CHANNEL","LEGAL_TRUST_READY","PUBLIC_LAUNCH"
]:
    if gates.get(gate)!="HOLD":
        errors.append(f"{gate} must remain HOLD")

existing=pack.get("exabytes_dns_state",{}).get("existing_records",{})
if existing.get("txt_count")!=1:
    errors.append("observed TXT count must be 1 after verification record application")
txt=existing.get("txt",[])
if len(txt)!=1 or txt[0].get("rdata")!="zoho-verification=zb36894990.zmverify.zoho.com":
    errors.append("applied Zoho TXT evidence drift")

mx=existing.get("mx",[])
if len(mx)!=1 or mx[0].get("rdata")!="0 lundusdigital.com":
    errors.append("existing root MX must remain unchanged until exact Zoho MX evidence")

draft=pack.get("change_set_draft",{})
if draft.get("status")!="DOMAIN_VERIFICATION_APPLIED_MX_SPF_DKIM_PENDING":
    errors.append("change-set state drift")
if draft.get("dns_mutation_authorized") is not False:
    errors.append("general change-set DNS mutation authority must remain false")
applied=draft.get("applied_pending_provider_verification",[])
if "TXT @ TTL 14440 = zoho-verification=zb36894990.zmverify.zoho.com" not in applied:
    errors.append("applied verification TXT missing from change-set evidence")

change=(docs/"LDS_EMAIL_DNS_CHANGESET_DRAFT.md").read_text()
for token in [
    "Zoho verification: **PENDING**",
    "Verify TXT Record",
    "@  MX  priority 0  lundusdigital.com",
    "General DNS mutation authority: **NO**"
]:
    if token not in change:
        errors.append(f"DNS change-set guard missing: {token}")

if errors:
    print("LDS Zoho Email DNS Readiness: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS Zoho Email DNS Readiness: PASS")
print("zoho_verification_txt=APPLIED_PENDING_ZOHO_VERIFICATION")
print("existing_mx=UNCHANGED")
print("mx_spf_dkim=HOLD")
print("general_dns_mutation_authorized=false")
