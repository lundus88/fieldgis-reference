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
if verify.get("status")!="APPLIED_PENDING_ZOHO_VERIFICATION":
    errors.append("Zoho verification TXT state drift")

mx=pack.get("exact_record_capture",{}).get("mx",{})
expected=[
    {"host":"@","priority":10,"value":"mx.zoho.com"},
    {"host":"@","priority":20,"value":"mx2.zoho.com"},
    {"host":"@","priority":50,"value":"mx3.zoho.com"}
]
if mx.get("records")!=expected:
    errors.append("Zoho MX evidence drift")
if mx.get("status")!="CAPTURED_NOT_APPLIED":
    errors.append("Zoho MX must remain captured-not-applied")

gates=domain.get("gate_status",{})
for gate in [
    "DNS_ZONE_PRESENT","EXISTING_DNS_INVENTORY_CAPTURED",
    "ZOHO_DOMAIN_VERIFICATION_RECORD_CAPTURED","ZOHO_DOMAIN_VERIFICATION_DNS_APPLIED",
    "ZOHO_MX_RECORDS_CAPTURED"
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

draft=pack.get("change_set_draft",{})
if draft.get("status")!="MX_CAPTURED_SPF_DKIM_PENDING":
    errors.append("change-set state drift")
if draft.get("dns_mutation_authorized") is not False:
    errors.append("general DNS mutation authority must remain false")
if "@ MX priority 0 lundusdigital.com" not in draft.get("delete_ready_for_human_application_review",[]):
    errors.append("old MX delete step missing")
for token in [
    "@ MX priority 10 mx.zoho.com",
    "@ MX priority 20 mx2.zoho.com",
    "@ MX priority 50 mx3.zoho.com"
]:
    if token not in draft.get("add_ready_for_human_application_review",[]):
        errors.append(f"Zoho MX add step missing: {token}")

change=(docs/"LDS_EMAIL_DNS_CHANGESET_DRAFT.md").read_text()
for token in [
    "@ MX priority 10 mx.zoho.com",
    "@ MX priority 20 mx2.zoho.com",
    "@ MX priority 50 mx3.zoho.com",
    "Do not change A, NS, CNAME or verification TXT records."
]:
    if token not in change:
        errors.append(f"DNS change-set guard missing: {token}")

if errors:
    print("LDS Zoho Email DNS Readiness: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS Zoho Email DNS Readiness: PASS")
print("zoho_mx=CAPTURED_NOT_APPLIED")
print("spf_dkim=HOLD")
print("general_dns_mutation_authorized=false")
