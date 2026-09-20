#!/usr/bin/env python3
from pathlib import Path
import json
import sys

path = Path("docs/commercial/LDS_DOMAIN_EMAIL_READINESS.json")
data = json.loads(path.read_text())
errors = []

if data.get("schema") != "lds.domain-email-readiness/1":
    errors.append("unexpected domain/email readiness schema")

domain = data.get("domain", {})
if domain.get("name") != "lundusdigital.com":
    errors.append("final commercial domain drift")
if domain.get("ownership_status") != "PASS":
    errors.append("domain ownership must be PASS")
if domain.get("registrar_portal_status") != "Active":
    errors.append("registrar portal status must remain Active")
if domain.get("auto_renew") != "Enabled":
    errors.append("auto-renew evidence drift")
if domain.get("next_due") != "2027-09-19":
    errors.append("next-due evidence drift")

dns = data.get("dns", {})
if dns.get("nameserver_change_authorized") is not False:
    errors.append("nameserver change must remain unauthorized")
if dns.get("production_binding_authorized") is not False:
    errors.append("Production domain binding must remain unauthorized")
if dns.get("dns_manager_access_verified") is not True:
    errors.append("DNS manager access evidence must be verified")
if dns.get("dns_zone_created") is not True:
    errors.append("DNS zone evidence must be present")

root = dns.get("root_domain", {})
if root.get("host") != "@" or root.get("target") != "103.7.9.22":
    errors.append("observed root A record evidence drift")
if root.get("status") != "OBSERVED_EXISTING_A_KEEP":
    errors.append("root A record must remain observed-existing/keep")

www = dns.get("www", {})
if www.get("host") != "www" or www.get("target") != "lundusdigital.com":
    errors.append("observed www CNAME evidence drift")
if www.get("status") != "OBSERVED_EXISTING_CNAME_KEEP":
    errors.append("www record must remain observed-existing/keep")

verification = dns.get("verification_records", [])
expected_verification = "zoho-verification=zb36894990.zmverify.zoho.com"
matched = [
    r for r in verification
    if r.get("type") == "TXT"
    and r.get("host") == "@"
    and r.get("value") == expected_verification
]
if not matched:
    errors.append("Zoho verification TXT evidence missing")
else:
    if matched[0].get("evidence_status") != "APPLIED_PENDING_ZOHO_VERIFICATION":
        errors.append("Zoho verification TXT state drift")
if dns.get("records_applied") is not True:
    errors.append("DNS evidence must record the approved verification TXT application")

email = data.get("email", {})
if email.get("provider") != "Zoho Mail":
    errors.append("email provider must be Zoho Mail")
if email.get("plan") != "Mail Lite 10 GB":
    errors.append("selected email plan must be Mail Lite 10 GB")
if email.get("provider_selection_status") != "PASS":
    errors.append("email provider selection must be PASS")
if email.get("subscription_purchase_authorized") is not True:
    errors.append("email subscription purchase evidence must record human-authorized purchase")
if email.get("subscription_purchased") is not True:
    errors.append("email subscription must be recorded as purchased")

sub = email.get("subscription_evidence", {})
if sub.get("status") != "PASS":
    errors.append("subscription evidence must be PASS")
if sub.get("term") != "1 year":
    errors.append("subscription term drift")
if sub.get("next_renewal_date") != "2027-09-19":
    errors.append("subscription renewal date drift")
if sub.get("charged_amount_evidence_status") != "PENDING_RECEIPT_OR_INVOICE":
    errors.append("charged amount evidence status must remain pending receipt/invoice")

if email.get("transactional_email_provider") != "Resend":
    errors.append("transactional email provider separation drift")
if email.get("official_commercial_email") != "hello@lundusdigital.com":
    errors.append("official commercial email evidence drift")
if email.get("official_commercial_email_status") != "CREATED_ACTIVE_PENDING_MAIL_ROUTING_VERIFICATION":
    errors.append("official commercial email must remain pending mail-routing verification")

channels = email.get("official_channel_selection", {})
expected_channels = {
    "primary_commercial_email": "hello@lundusdigital.com",
    "support_complaint_email": "support@lundusdigital.com",
    "billing_email": "billing@lundusdigital.com",
}
for key, value in expected_channels.items():
    entry = channels.get(key, {})
    if entry.get("value") != value:
        errors.append(f"{key} selection drift")
    if entry.get("status") != "SELECTED_NOT_VERIFIED":
        errors.append(f"{key} must remain selected-not-verified")

architecture = email.get("mailbox_architecture", {})
if architecture.get("licensed_users_planned") != 1:
    errors.append("initial mailbox architecture must plan one licensed user")
if architecture.get("licensed_users_purchased") != 1:
    errors.append("one licensed user must be recorded as purchased")
if architecture.get("primary_mailbox") != "hello@lundusdigital.com":
    errors.append("primary mailbox drift")
if architecture.get("primary_mailbox_status") != "CREATED_ACTIVE_PENDING_MAIL_ROUTING_VERIFICATION":
    errors.append("primary mailbox must remain pending mail-routing verification")
if architecture.get("alias_status") != "SELECTED_NOT_VERIFIED":
    errors.append("aliases must remain selected-not-verified")
aliases = set(architecture.get("aliases", []))
for address in ["support@lundusdigital.com", "billing@lundusdigital.com"]:
    if address not in aliases:
        errors.append(f"selected alias missing: {address}")

mailbox_evidence = email.get("mailbox_creation_evidence", {})
if mailbox_evidence.get("mailbox") != "hello@lundusdigital.com":
    errors.append("mailbox creation evidence drift")
if mailbox_evidence.get("status") != "CREATED_ACTIVE":
    errors.append("primary mailbox creation must be evidenced as active")

provider_records = email.get("exact_provider_records", {})
provider_verify = provider_records.get("domain_verification", {})
if provider_verify.get("type") != "TXT" or provider_verify.get("host") != "@":
    errors.append("provider verification TXT metadata drift")
if provider_verify.get("value") != expected_verification:
    errors.append("provider verification TXT value drift")
if provider_verify.get("status") != "APPLIED_PENDING_ZOHO_VERIFICATION":
    errors.append("provider verification TXT must remain pending Zoho verification")

expected_mx = [
    {"host": "@", "priority": 10, "value": "mx.zoho.com", "status": "CAPTURED_NOT_APPLIED"},
    {"host": "@", "priority": 20, "value": "mx2.zoho.com", "status": "CAPTURED_NOT_APPLIED"},
    {"host": "@", "priority": 50, "value": "mx3.zoho.com", "status": "CAPTURED_NOT_APPLIED"},
]
if provider_records.get("mx") != expected_mx:
    errors.append("exact Zoho MX evidence drift")

spf_exact = provider_records.get("spf", {})
if spf_exact.get("host") is not None or spf_exact.get("value") is not None:
    errors.append("SPF exact provider evidence must remain unset")
if spf_exact.get("status") != "EVIDENCE_REQUIRED":
    errors.append("SPF must remain evidence-required")

dkim_exact = provider_records.get("dkim", {})
if any(dkim_exact.get(k) is not None for k in ["selector", "host", "value"]):
    errors.append("DKIM exact provider evidence must remain unset")
if dkim_exact.get("status") != "EVIDENCE_REQUIRED":
    errors.append("DKIM must remain evidence-required")

dmarc_exact = provider_records.get("dmarc", {})
if dmarc_exact.get("host") != "_dmarc" or dmarc_exact.get("value") is not None:
    errors.append("DMARC readiness evidence drift")
if dmarc_exact.get("status") != "DEFER_UNTIL_SPF_DKIM_VERIFIED":
    errors.append("DMARC must remain deferred until SPF/DKIM verification")

if email.get("mx", {}).get("status") != "CAPTURED_NOT_APPLIED":
    errors.append("MX must remain captured-not-applied")
if email.get("spf", {}).get("status") != "HOLD_EVIDENCE_REQUIRED":
    errors.append("SPF must remain HOLD_EVIDENCE_REQUIRED")
if email.get("dkim", {}).get("status") != "HOLD_EVIDENCE_REQUIRED":
    errors.append("DKIM must remain HOLD_EVIDENCE_REQUIRED")
if email.get("dmarc", {}).get("status") != "HOLD_UNTIL_SPF_DKIM_VERIFIED":
    errors.append("DMARC must remain HOLD_UNTIL_SPF_DKIM_VERIFIED")

gates = data.get("gate_status", {})
expected = {
    "FINAL_COMMERCIAL_DOMAIN": "PASS",
    "DOMAIN_OWNERSHIP_VERIFIED": "PASS",
    "EMAIL_PROVIDER_SELECTED": "PASS",
    "EMAIL_SUBSCRIPTION_ACTIVE": "PASS",
    "OFFICIAL_CHANNELS_SELECTED": "PASS",
    "DNS_ZONE_PRESENT": "PASS",
    "EXISTING_DNS_INVENTORY_CAPTURED": "PASS",
    "ZOHO_DOMAIN_VERIFICATION_RECORD_CAPTURED": "PASS",
    "ZOHO_DOMAIN_VERIFICATION_DNS_APPLIED": "PASS",
    "OFFICIAL_MAILBOX_CREATED": "PASS",
    "ZOHO_MX_RECORDS_CAPTURED": "PASS",
    "ZOHO_EXACT_DNS_RECORDS_CAPTURED": "HOLD",
    "DNS_PRODUCTION_BINDING": "HOLD",
    "EMAIL_DNS_AUTHENTICATION": "HOLD",
    "OFFICIAL_COMMERCIAL_EMAIL": "HOLD",
    "SUPPORT_COMPLAINT_CHANNEL": "HOLD",
    "LEGAL_TRUST_READY": "HOLD",
    "PUBLIC_LAUNCH": "HOLD",
    "ZOHO_DOMAIN_OWNERSHIP_VERIFIED": "HOLD",
}
for key, value in expected.items():
    if gates.get(key) != value:
        errors.append(f"{key} must be {value}")

authority = data.get("authority", {})
for key in [
    "dns_mutation_authorized",
    "nameserver_change_authorized",
    "email_activation_authorized",
    "vercel_production_binding_authorized",
    "payment_activation_authorized",
    "public_launch_authorized",
]:
    if authority.get(key) is not False:
        errors.append(f"{key} must remain false")

if errors:
    print("LDS domain/email readiness: FAIL")
    for error in errors:
        print("-", error)
    sys.exit(1)

print("LDS domain/email readiness: PASS")
print("domain=lundusdigital.com")
print("domain_ownership=PASS")
print("email_provider=Zoho Mail")
print("email_plan=Mail Lite 10 GB")
print("mailbox_created=PASS_PENDING_ROUTING")
print("zoho_verification_txt=APPLIED_PENDING_PROVIDER_VERIFICATION")
print("zoho_mx=CAPTURED_NOT_APPLIED")
print("spf_dkim=HOLD_EVIDENCE_REQUIRED")
print("dns_mutation=HOLD")
print("email_dns_authentication=HOLD")
print("official_commercial_email=HOLD")
print("production_binding=HOLD")
