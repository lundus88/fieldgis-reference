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

dns = data.get("dns", {})
if dns.get("nameserver_change_authorized") is not False:
    errors.append("nameserver change must remain unauthorized")
if dns.get("production_binding_authorized") is not False:
    errors.append("Production domain binding must remain unauthorized")
if dns.get("dns_manager_access_verified") is not True:
    errors.append("DNS manager access must remain verified")
if dns.get("dns_zone_created") is not True:
    errors.append("DNS zone evidence must remain present")
if dns.get("exact_zoho_records_captured") is not True:
    errors.append("verified Zoho DNS evidence must be captured")

email = data.get("email", {})
if email.get("provider") != "Zoho Mail":
    errors.append("email provider must be Zoho Mail")
if email.get("plan") != "Mail Lite 10 GB":
    errors.append("email plan drift")
if email.get("official_commercial_email") != "hello@lundusdigital.com":
    errors.append("official commercial email drift")
if email.get("official_commercial_email_status") != "PASS_OUTBOUND_DELIVERY_AND_AUTHENTICATION":
    errors.append("official commercial email must reflect verified outbound delivery/authentication")
if email.get("sender_display_name") != "LUNDUS DIGITAL SYSTEMS":
    errors.append("sender display name drift")
if email.get("sender_display_name_status") != "PASS":
    errors.append("sender display name UAT must be PASS")

auth = email.get("authentication", {})
for key in ["external_delivery_status", "spf", "dkim", "dmarc"]:
    if auth.get(key) != "PASS":
        errors.append(f"{key} must be PASS")
if auth.get("dkim_domain") != "lundusdigital.com":
    errors.append("DKIM domain drift")

architecture = email.get("mailbox_architecture", {})
if architecture.get("primary_mailbox") != "hello@lundusdigital.com":
    errors.append("primary mailbox drift")
if architecture.get("primary_mailbox_status") != "ACTIVE":
    errors.append("primary mailbox must be ACTIVE")
if architecture.get("alias_receive_status") != "PASS":
    errors.append("alias receive routing must be PASS")
aliases = set(architecture.get("aliases", []))
for address in [
    "support@lundusdigital.com",
    "billing@lundusdigital.com",
    "dmarc@lundusdigital.com",
]:
    if address not in aliases:
        errors.append(f"alias missing: {address}")

uat = email.get("uat", {})
for key in [
    "hello_outbound_to_gmail",
    "sender_display_name",
    "support_alias_inbound_to_hello",
    "billing_alias_inbound_to_hello",
    "dmarc_alias_inbound_to_hello",
    "overall_basic_email_uat",
]:
    if uat.get(key) != "PASS":
        errors.append(f"UAT evidence must be PASS: {key}")

records = email.get("exact_provider_records", {})
mx = records.get("mx", [])
expected_mx = [
    {"host": "@", "priority": 10, "value": "mx.zoho.com", "status": "VERIFIED"},
    {"host": "@", "priority": 20, "value": "mx2.zoho.com", "status": "VERIFIED"},
    {"host": "@", "priority": 50, "value": "mx3.zoho.com", "status": "VERIFIED"},
]
if mx != expected_mx:
    errors.append("verified Zoho MX evidence drift")

spf = records.get("spf", {})
if spf.get("host") != "@" or spf.get("value") != "v=spf1 include:zohomail.com ~all" or spf.get("status") != "VERIFIED":
    errors.append("verified SPF evidence drift")

dkim = records.get("dkim", {})
if dkim.get("selector") != "ld2026" or dkim.get("host") != "ld2026._domainkey" or dkim.get("status") != "VERIFIED":
    errors.append("verified DKIM evidence drift")
if dkim.get("value") is not None:
    errors.append("DKIM public key must not be reconstructed in repository evidence")

dmarc = records.get("dmarc", {})
expected_dmarc = "v=DMARC1; p=none; rua=mailto:dmarc@lundusdigital.com; ruf=mailto:dmarc@lundusdigital.com; sp=none; adkim=r; aspf=r; pct=100"
if dmarc.get("host") != "_dmarc" or dmarc.get("value") != expected_dmarc or dmarc.get("status") != "VERIFIED":
    errors.append("verified DMARC evidence drift")

gates = data.get("gate_status", {})
expected_gates = {
    "FINAL_COMMERCIAL_DOMAIN": "PASS",
    "DOMAIN_OWNERSHIP_VERIFIED": "PASS",
    "EMAIL_PROVIDER_SELECTED": "PASS",
    "EMAIL_SUBSCRIPTION_ACTIVE": "PASS",
    "OFFICIAL_CHANNELS_SELECTED": "PASS",
    "EMAIL_DNS_AUTHENTICATION": "PASS",
    "OFFICIAL_COMMERCIAL_EMAIL": "PASS",
    "SUPPORT_COMPLAINT_CHANNEL": "PASS_INBOUND",
    "BILLING_CHANNEL": "PASS_INBOUND",
    "DMARC_REPORTING_CHANNEL": "PASS_INBOUND",
    "ZOHO_DOMAIN_OWNERSHIP_VERIFIED": "PASS",
    "ZOHO_MX_VERIFIED": "PASS",
    "ZOHO_SPF_VERIFIED": "PASS",
    "ZOHO_DKIM_VERIFIED": "PASS",
    "ZOHO_DMARC_VERIFIED": "PASS",
    "BASIC_EMAIL_UAT": "PASS",
    "DNS_PRODUCTION_BINDING": "HOLD",
    "LEGAL_TRUST_READY": "HOLD",
    "PUBLIC_LAUNCH": "HOLD",
}
for key, value in expected_gates.items():
    if gates.get(key) != value:
        errors.append(f"{key} must be {value}")

authority = data.get("authority", {})
if authority.get("email_activation_authorized") is not True:
    errors.append("email activation must record the completed human authorization")
for key in [
    "dns_mutation_authorized",
    "nameserver_change_authorized",
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
print("email_provider=Zoho Mail")
print("official_email=PASS")
print("spf=PASS")
print("dkim=PASS")
print("dmarc=PASS")
print("alias_inbound=PASS")
print("basic_email_uat=PASS")
print("production_binding=HOLD")
print("public_launch=HOLD")
