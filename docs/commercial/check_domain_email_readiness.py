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
if email.get("provider") is not None:
    errors.append("email provider must remain unselected until explicit decision")
if email.get("provider_selection_status") != "PENDING":
    errors.append("email provider selection must remain PENDING")
if email.get("official_commercial_email") is not None:
    errors.append("official commercial email must remain unset before mailbox verification")
planned = set(email.get("mailboxes_planned", []))
for address in [
    "hello@lundusdigital.com",
    "support@lundusdigital.com",
    "billing@lundusdigital.com",
]:
    if address not in planned:
        errors.append(f"planned mailbox missing: {address}")
for auth_key in ["mx", "spf", "dkim", "dmarc"]:
    if email.get(auth_key, {}).get("status") != "HOLD_NOT_APPLIED":
        errors.append(f"{auth_key} must remain HOLD_NOT_APPLIED")

gates = data.get("gate_status", {})
expected = {
    "FINAL_COMMERCIAL_DOMAIN": "PASS",
    "DOMAIN_OWNERSHIP_VERIFIED": "PASS",
    "DNS_PRODUCTION_BINDING": "HOLD",
    "EMAIL_PROVIDER_SELECTED": "HOLD",
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
print("dns_mutation=HOLD")
print("email_provider=PENDING")
print("production_binding=HOLD")
