#!/usr/bin/env python3
from pathlib import Path
import json, sys

root = Path("commercial/lundus-digital-systems")
required = [
    "index.html","services.html","about.html","contact.html","faq.html",
    "privacy.html","terms.html","refund.html","checkout.html","order.html",
    "styles.css","site.js","analytics-contract.json","lead-intake-contract.json",
    "FIRST_COMMERCIAL_OFFER_RC.md","README.md",
]
errors=[]

for name in required:
    if not (root/name).is_file():
        errors.append(f"missing required surface: {name}")

html = {p.name:p.read_text() for p in root.glob("*.html")}

for name, text in html.items():
    if "LUNDUS DIGITAL SYSTEMS" not in text:
        errors.append(f"{name}: brand missing")
    if "http://127.0.0.1" in text or "localhost" in text:
        errors.append(f"{name}: local runtime reference leaked")

index = html.get("index.html","")
for link in ["services.html","contact.html","privacy.html","terms.html","refund.html","checkout.html"]:
    if link not in index:
        errors.append(f"index.html: missing navigation/link {link}")

contact = html.get("contact.html","")
if "data-rc-form" not in contact:
    errors.append("contact.html: quotation form is not explicitly RC-blocked")
for token in ['name="submission_id"','name="turnstile_token"','name="website"','data-turnstile-placeholder']:
    if token not in contact:
        errors.append(f"contact.html: missing lead-intake field/guard {token}")

checkout = html.get("checkout.html","")
for phrase in ["Live payment is not yet enabled","intentionally blocks customer charging","server-authoritative amount","signed backend callback"]:
    if phrase not in checkout:
        errors.append(f"checkout.html: missing fail-closed phrase: {phrase}")

site_js = (root/"site.js").read_text() if (root/"site.js").exists() else ""
if "preventDefault()" not in site_js or "No data was sent" not in site_js:
    errors.append("site.js: RC form submission block missing")
if "crypto.randomUUID()" not in site_js:
    errors.append("site.js: submission UUID generation missing")
for token in ["billplz.com","functions/v1/vl-billplz-create-production","fetch("]:
    if token in site_js:
        errors.append(f"site.js: live network/payment token forbidden in RC: {token}")

for policy in ["privacy.html","terms.html","refund.html"]:
    if "Effective date: to be confirmed before public commercial launch." not in html.get(policy,""):
        errors.append(f"{policy}: RC effective-date guard missing")

analytics_path=root/"analytics-contract.json"
if analytics_path.exists():
    data=json.loads(analytics_path.read_text())
    if data.get("schema")!="lds.analytics-contract/1":
        errors.append("analytics: unexpected schema")
    keys={e.get("key") for e in data.get("events",[])}
    for key in ["page_view","cta_quote","checkout_start","payment_confirmed_backend","order_fulfilled"]:
        if key not in keys:
            errors.append(f"analytics: missing {key}")

lead_path=root/"lead-intake-contract.json"
if lead_path.exists():
    lead=json.loads(lead_path.read_text())
    if lead.get("schema")!="lds.public-lead-intake/1":
        errors.append("lead intake: unexpected schema")
    if lead.get("public_endpoint")!="/api/public/leads/intake":
        errors.append("lead intake: endpoint drift")
    required_fields=set(lead.get("required_fields",[]))
    for key in ["submission_id","name","email","service","message","turnstile_token"]:
        if key not in required_fields:
            errors.append(f"lead intake: missing required field {key}")
    if lead.get("client_to_lunduslead_direct_write") is not False:
        errors.append("lead intake: browser-to-internal-CRM direct write must be false")
    forbidden=set(lead.get("forbidden_actions",[]))
    for key in ["auto_quotation","auto_pricing","auto_payment","auto_sale","direct_browser_write_to_internal_crm","expose_internal_crm_credentials"]:
        if key not in forbidden:
            errors.append(f"lead intake: missing forbidden action {key}")
    if lead.get("handoff")!="server-to-server into LundusLead after connector validation":
        errors.append("lead intake: internal CRM handoff is not server-to-server")

offer=(root/"FIRST_COMMERCIAL_OFFER_RC.md").read_text() if (root/"FIRST_COMMERCIAL_OFFER_RC.md").exists() else ""
for token in [
    "Custom Digital Systems & Automation — Quotation-Led Implementation",
    "offer_type = customer_quote",
    "customer_account_id",
    "valid_until",
    "OFFER_LOCKED = YES",
    "human-approved customer quotes",
]:
    if token not in offer:
        errors.append(f"first offer RC: missing {token}")

readme=(root/"README.md").read_text() if (root/"README.md").exists() else ""
for token in ["OFFER_LOCKED = NO","no live checkout","no customer charging","no Production deployment"]:
    if token not in readme:
        errors.append(f"README: missing guardrail {token}")

if errors:
    print("LDS commercial surface contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS commercial surface contract: PASS")
print(f"required_surfaces={len(required)} html_pages={len(html)}")
