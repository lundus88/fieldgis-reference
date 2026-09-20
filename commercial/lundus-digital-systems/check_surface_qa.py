#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
import sys

root=Path("commercial/lundus-digital-systems")
errors=[]

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
        self.titles=[]
        self.h1=0
        self.lang=None
        self.viewport=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="html":
            self.lang=a.get("lang")
        elif tag=="a" and a.get("href"):
            self.links.append(a["href"])
        elif tag=="meta" and a.get("name","").lower()=="viewport":
            self.viewport=bool(a.get("content"))
        elif tag=="h1":
            self.h1+=1
    def handle_data(self,data):
        pass

pages=list(root.glob("*.html"))
if not pages:
    errors.append("no HTML pages found")

for page in pages:
    parser=PageParser()
    parser.feed(page.read_text())
    if parser.lang not in ("en","ms"):
        errors.append(f"{page.name}: missing/unsupported html lang")
    if not parser.viewport:
        errors.append(f"{page.name}: viewport meta missing")
    if parser.h1 != 1:
        errors.append(f"{page.name}: expected exactly one h1, got {parser.h1}")

    for href in parser.links:
        u=urlparse(href)
        if u.scheme in ("http","https","mailto","tel"):
            continue
        target=href.split("#",1)[0].split("?",1)[0]
        if not target:
            continue
        if target.startswith("/"):
            errors.append(f"{page.name}: root-relative link not allowed in static RC: {href}")
            continue
        if not (root/target).exists():
            errors.append(f"{page.name}: broken local link -> {href}")

index=(root/"index.html").read_text()
for token in [
    "services.html","contact.html","privacy.html","terms.html",
    "refund.html","checkout.html","maklumat-urusniaga.html"
]:
    if token not in index:
        errors.append(f"index.html: missing required navigation target {token}")

contact=(root/"contact.html").read_text()
for token in [
    'name="submission_id"',
    'name="turnstile_token"',
    'name="website"',
    'name="name"',
    'name="email"',
    'name="service"',
    'name="message"',
    "No information is transmitted in this Release Candidate."
]:
    if token not in contact:
        errors.append(f"contact.html: missing form/control token {token}")

checkout=(root/"checkout.html").read_text()
for token in [
    "Live payment is not yet enabled.",
    "intentionally blocks customer charging",
    "server-authoritative amount",
    "signed backend callback"
]:
    if token not in checkout:
        errors.append(f"checkout.html: missing HOLD guard {token}")

styles=(root/"styles.css").read_text()
if "@media(max-width:860px)" not in styles.replace(" ",""):
    errors.append("styles.css: responsive mobile media query missing")

site=(root/"site.js").read_text()
for forbidden in ["billplz.com","SUPABASE_SERVICE_ROLE_KEY","RESEND_PRODUCTION_API_KEY","fetch("]:
    if forbidden in site:
        errors.append(f"site.js: forbidden live/secret token {forbidden}")
for token in ["preventDefault()","crypto.randomUUID()","page_view"]:
    if token not in site:
        errors.append(f"site.js: missing RC/measurement guard {token}")

if errors:
    print("LDS commercial surface QA: FAIL")
    for e in errors:
        print("-",e)
    sys.exit(1)

print("LDS commercial surface QA: PASS")
print(f"html_pages={len(pages)} local_links=validated responsive=validated rc_network=blocked")
