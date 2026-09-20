#!/usr/bin/env python3
from pathlib import Path
import json, sys

root = Path("commercial/lundus-digital-systems")
required = [
    "index.html","services.html","about.html","contact.html","faq.html",
    "privacy.html","terms.html","refund.html","privacy-bm.html","terms-bm.html","refund-bm.html",
    "checkout.html","order.html",
    "styles.css","site.js","analytics-contract.json","lead-intake-contract.json",
    "legal-trust-contract.json","maklumat-urusniaga.html",
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
for link in ["services.html","contact.html","privacy.html","terms.html","refund.html","checkout.html","maklumat-urusniaga.html"]:
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
    text=html.get(policy,"")
    for token in ["Version:","1.0","Effective date:","20 September 2026"]:
        if token not in text:
            errors.append(f"{policy}: approved policy version/effective-date guard missing {token}")
for policy in ["privacy-bm.html","terms-bm.html","refund-bm.html"]:
    text=html.get(policy,"")
    for token in ["Versi:","1.0","Tarikh kuat kuasa:","20 September 2026"]:
        if token not in text:
            errors.append(f"{policy}: BM approved policy version/effective-date guard missing {token}")

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
    if lead.get("client_to_lunduslead_direct_write") is not False:
        errors.append("lead intake: browser-to-internal-CRM direct write must be false")

legal_path=root/"legal-trust-contract.json"
if legal_path.exists():
    legal=json.loads(legal_path.read_text())
    if legal.get("schema")!="lds.legal-trust-readiness/1":
        errors.append("legal trust: unexpected schema")
    if legal.get("production_ready") is not False:
        errors.append("legal trust: RC must remain production_ready=false")
    verified=legal.get("verified_values",{})
    for key in ["registered_entity_name","registration_number","final_commercial_domain","registration_status"]:
        if not verified.get(key):
            errors.append(f"legal trust: verified value missing {key}")
    pending=set(legal.get("pending_verified_values",[]))
    expected_pending={"ld_dedicated_business_phone","registered_business_address_publication_approval"}
    if pending != expected_pending:
        errors.append(f"legal trust: pending verified values drift: {sorted(pending)}")
    if verified.get("official_email") != "hello@lundusdigital.com" or verified.get("official_email_status") != "PASS":
        errors.append("legal trust: verified official email evidence drift")
    if verified.get("support_complaint_channel") != "support@lundusdigital.com" or verified.get("support_complaint_channel_status") != "PASS_INBOUND":
        errors.append("legal trust: verified support channel evidence drift")
    if verified.get("official_phone_evidence_status") != "VERIFIED_PRESENT_VALUE_REDACTED":
        errors.append("legal trust: official phone evidence must remain verified/redacted")
    if verified.get("trade_address_evidence_status") != "VERIFIED_PRESENT_VALUE_REDACTED":
        errors.append("legal trust: trade address evidence must remain verified/redacted")
    required_disclosures=set(legal.get("required_disclosures_bm",[]))
    for key in ["supplier_or_company_name","website_address","email","telephone","trade_address","service_main_characteristics","full_price_including_tax_and_other_cost","payment_method","sale_terms","estimated_supply_time"]:
        if key not in required_disclosures:
            errors.append(f"legal trust: missing BM disclosure contract {key}")

bm=(root/"maklumat-urusniaga.html").read_text() if (root/"maklumat-urusniaga.html").exists() else ""
for token in ['lang="ms"',"Maklumat Pembekal & Urus Niaga","202603248473 (003891235-V)","lundusdigital.com","BELUM DISEDIAKAN / DISAHKAN","MENUNGGU KELULUSAN PENERBITAN","Harga penuh","Kaedah pembayaran","Anggaran masa pembekalan perkhidmatan","Pembetulan kesilapan & pengakuterimaan pesanan"]:
    if token not in bm:
        errors.append(f"BM disclosure: missing {token}")

if errors:
    print("LDS commercial surface contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)

print("LDS commercial surface contract: PASS")
print(f"required_surfaces={len(required)} html_pages={len(html)}")
