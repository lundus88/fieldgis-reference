#!/usr/bin/env python3
from pathlib import Path
import json
import sys

docs = Path("docs/commercial")
errors = []

domain = json.loads((docs / "LDS_DOMAIN_EMAIL_READINESS.json").read_text())
pack = json.loads((docs / "LDS_ZOHO_EMAIL_DNS_READINESS.json").read_text())

if domain.get("schema") != "lds.domain-email-readiness/1":
    errors.append("domain/email schema drift")
if pack.get("schema") != "lds.zoho-email-dns-readiness/1":
    errors.append("Zoho readiness schema drift")
if pack.get("status") != "PASS_BASIC_EMAIL_UAT":
    errors.append("Zoho readiness pack must reflect PASS_BASIC_EMAIL_UAT")

capture = pack.get("exact_record_capture", {})
verify = capture.get("domain_verification", {})
if verify.get("status") != "VERIFIED":
    errors.append("Zoho ownership verification must be VERIFIED")

mx = capture.get("mx", {})
expected_mx = [
    {"host": "@", "priority": 10, "value": "mx.zoho.com"},
    {"host": "@", "priority": 20, "value": "mx2.zoho.com"},
    {"host": "@", "priority": 50, "value": "mx3.zoho.com"},
]
if mx.get("records") != expected_mx:
    errors.append("Zoho MX evidence drift")
if mx.get("status") != "VERIFIED":
    errors.append("Zoho MX must be VERIFIED")

spf = capture.get("spf", {})
if spf.get("host") != "@" or spf.get("value") != "v=spf1 include:zohomail.com ~all" or spf.get("status") != "VERIFIED":
    errors.append("Zoho SPF evidence drift")

dkim = capture.get("dkim", {})
if dkim.get("selector") != "ld2026":
    errors.append("DKIM selector drift")
if dkim.get("host") != "ld2026._domainkey":
    errors.append("DKIM host drift")
if dkim.get("status") != "VERIFIED":
    errors.append("DKIM must be VERIFIED")
if dkim.get("value") is not None:
    errors.append("DKIM public key must not be reconstructed from screenshot evidence")

dmarc = capture.get("dmarc", {})
expected_dmarc = "v=DMARC1; p=none; rua=mailto:dmarc@lundusdigital.com; ruf=mailto:dmarc@lundusdigital.com; sp=none; adkim=r; aspf=r; pct=100"
if dmarc.get("host") != "_dmarc" or dmarc.get("value") != expected_dmarc or dmarc.get("status") != "VERIFIED":
    errors.append("DMARC evidence drift")

uat = pack.get("external_authentication_uat", {})
for key in ["spf", "dkim", "dmarc", "delivery_status"]:
    if uat.get(key) != "PASS":
        errors.append(f"external authentication UAT must be PASS: {key}")
if uat.get("from") != "LUNDUS DIGITAL SYSTEMS <hello@lundusdigital.com>":
    errors.append("sender identity drift")
if uat.get("dkim_domain") != "lundusdigital.com":
    errors.append("DKIM domain drift")

mailbox = pack.get("mailbox_state", {})
if mailbox.get("primary_mailbox") != "hello@lundusdigital.com":
    errors.append("primary mailbox drift")
if mailbox.get("primary_mailbox_status") != "ACTIVE":
    errors.append("primary mailbox must be ACTIVE")
if mailbox.get("sender_display_name") != "LUNDUS DIGITAL SYSTEMS":
    errors.append("sender display-name drift")
if mailbox.get("sender_display_name_status") != "PASS":
    errors.append("sender display-name UAT must be PASS")
if mailbox.get("basic_email_uat") != "PASS":
    errors.append("basic email UAT must be PASS")

aliases = mailbox.get("aliases", {})
for address in ["support@lundusdigital.com", "billing@lundusdigital.com", "dmarc@lundusdigital.com"]:
    if aliases.get(address, {}).get("receive_to_primary") != "PASS":
        errors.append(f"alias receive UAT must be PASS: {address}")

checks = pack.get("post_apply_checks", {})
for key in [
    "zoho_domain_verification",
    "zoho_mx_verification",
    "outbound_hello_to_external_gmail",
    "sender_display_name",
    "support_alias_receive",
    "billing_alias_receive",
    "dmarc_alias_receive",
    "spf_alignment",
    "dkim_alignment",
    "dmarc_alignment",
]:
    if checks.get(key) != "PASS":
        errors.append(f"post-apply check must be PASS: {key}")

draft = pack.get("change_set_draft", {})
if draft.get("status") != "EMAIL_DNS_APPLIED_AND_VERIFIED":
    errors.append("change-set must be recorded as applied and verified")
if draft.get("further_dns_mutation_authorized") is not False:
    errors.append("further DNS mutation must remain unauthorized")
if draft.get("legacy_root_mx_removed") is not True:
    errors.append("legacy root MX removal evidence missing")
if draft.get("website_records_preserved") is not True:
    errors.append("website records must remain preserved")

change = (docs / "LDS_EMAIL_DNS_CHANGESET_DRAFT.md").read_text()
for token in [
    "EMAIL DNS APPLIED AND VERIFIED",
    "SPF: **PASS**",
    "DKIM: **PASS**",
    "DMARC: **PASS**",
    "support@lundusdigital.com",
    "billing@lundusdigital.com",
    "dmarc@lundusdigital.com",
    "Production website binding: **HOLD**",
    "Public launch: **HOLD**",
]:
    if token not in change:
        errors.append(f"as-built record guard missing: {token}")

if pack.get("dns_mutation_authorized") is not False:
    errors.append("general DNS mutation authority must remain false")
if pack.get("production_website_binding_authorized") is not False:
    errors.append("Production website binding must remain unauthorized")
if pack.get("payment_activation_authorized") is not False:
    errors.append("payment activation must remain unauthorized")
if pack.get("public_launch_authorized") is not False:
    errors.append("public launch must remain unauthorized")

if errors:
    print("LDS Zoho Email DNS Readiness: FAIL")
    for error in errors:
        print("-", error)
    sys.exit(1)

print("LDS Zoho Email DNS Readiness: PASS")
print("domain_ownership=PASS")
print("mx=PASS")
print("spf=PASS")
print("dkim=PASS")
print("dmarc=PASS")
print("alias_inbound=PASS")
print("basic_email_uat=PASS")
print("production_binding=HOLD")
print("public_launch=HOLD")
