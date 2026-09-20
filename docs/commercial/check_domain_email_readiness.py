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
if dns.get("records_applied") is not False:
    errors.append("DNS records must remain unapplied in readiness mode")
if dns.get("production_binding_authorized") is not False:
    errors.append("Production domain binding must remain unauthorized")
for key in ["root_domain", "www"]:
    entry = dns.get(key, {})
    if entry.get("status") != "HOLD_NOT_APPLIED":
        errors.append(f"{key} must remain HOLD_NOT_APPLIED")
    if entry.get("target") is not None:
        errors.append(f"{key} target must remain null until exact provider value is approved")

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
if sub.get("credit_earned_myr") != 7.20:
    errors.append("subscription credit evidence drift")
if sub.get("charged_amount_myr") is not None:
    errors.append("charged amount must remain null until receipt/invoice evidence is captured")
if sub.get("charged_amount_evidence_status") != "PENDING_RECEIPT_OR_INVOICE":
    errors.append("charged amount evidence status must remain pending receipt/invoice")

if email.get("transactional_email_provider") != "Resend":
    errors.append("transactional email provider separation drift")
if email.get("official_commercial_email") is not None:
    errors.append("official commercial email must remain unset before mailbox verification")

architecture = email.get("mailbox_architecture", {})
if architecture.get("licensed_users_planned") != 1:
    errors.append("initial mailbox architecture must plan one licensed user")
if architecture.get("licensed_users_purchased") != 1:
    errors.append("one licensed user must be recorded as purchased")
if architecture.get("primary_mailbox") != "hello@lundusdigital.com":
    errors.append("primary mailbox plan drift")
if architecture.get("primary_mailbox_status") != "PLANNED_NOT_YET_VERIFIED":
    errors.append("primary mailbox must remain unverified")
if architecture.get("alias_status") != "PLANNED_NOT_YET_VERIFIED":
    errors.append("aliases must remain unverified")
aliases = set(architecture.get("aliases", []))
for address in ["support@lundusdigital.com", "billing@lundusdigital.com"]:
    if address not in aliases:
        errors.append(f"planned alias missing: {address}")

planned = set(email.get("mailboxes_planned", []))
for address in [
    "hello@lundusdigital.com",
    "support@lundusdigital.com",
    "billing@lundusdigital.com",
]:
    if address not in planned:
        errors.append(f"planned address missing: {address}")

for auth_key in ["mx", "spf", "dkim", "dmarc"]:
    if email.get(auth_key, {}).get("status") != "HOLD_NOT_APPLIED":
        errors.append(f"{auth_key} must remain HOLD_NOT_APPLIED")

gates = data.get("gate_status", {})
expected = {
    "FINAL_COMMERCIAL_DOMAIN": "PASS",
    "DOMAIN_OWNERSHIP_VERIFIED": "PASS",
    "DNS_PRODUCTION_BINDING": "HOLD",
    "EMAIL_PROVIDER_SELECTED": "PASS",
    "EMAIL_SUBSCRIPTION_ACTIVE": "PASS",
    "EMAIL_DNS_AUTHENTICATION": "HOLD",
    "OFFICIAL_COMMERCIAL_EMAIL": "HOLD",
    "LEGAL_TRUST_READY": "HOLD",
    "PUBLIC_LAUNCH": "HOLD",
}
for key, value in expected.items():
    if gates.get(key) != value:
        errors.append(f"{key} must be {value}")

authority = data.get("authority", {})
for key in [
    "dns_mutation_authorized",
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
print("email_subscription=PASS")
print("charged_amount=PENDING_RECEIPT_OR_INVOICE")
print("dns_mutation=HOLD")
print("email_dns_authentication=HOLD")
print("official_commercial_email=HOLD")
print("production_binding=HOLD")
