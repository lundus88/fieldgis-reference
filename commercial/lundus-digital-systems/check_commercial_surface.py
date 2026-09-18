#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

root = Path("commercial/lundus-digital-systems")
required = [
    "index.html","services.html","about.html","contact.html","faq.html",
    "privacy.html","terms.html","refund.html","checkout.html","order.html",
    "styles.css","site.js","analytics-contract.json","README.md",
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

checkout = html.get("checkout.html","")
for phrase in ["Live payment is not yet enabled","intentionally blocks customer charging","server-authoritative amount","signed backend callback"]:
    if phrase not in checkout:
        errors.append(f"checkout.html: missing fail-closed phrase: {phrase}")

site_js = (root/"site.js").read_text() if (root/"site.js").exists() else ""
if "preventDefault()" not in site_js or "No data was sent" not in site_js:
    errors.append("site.js: RC form submission block missing")
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
