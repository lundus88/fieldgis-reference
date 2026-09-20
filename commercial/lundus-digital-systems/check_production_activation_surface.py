#!/usr/bin/env python3
from pathlib import Path
import sys

root=Path("commercial/lundus-digital-systems")
errors=[]
hold_reasons=[]

pages=list(root.glob("*.html"))
if not pages:
    errors.append("no commercial pages found")

for p in pages:
    t=p.read_text()
    if 'name="robots" content="noindex,nofollow,noarchive"' not in t:
        errors.append(f"{p.name}: RC noindex guard missing")

robots=(root/"robots.txt").read_text() if (root/"robots.txt").exists() else ""
if "Disallow: /" not in robots:
    errors.append("robots.txt must block crawling in RC")

# Production activation blockers intentionally expected in RC.
for token,label in [
    ("BELUM DISAHKAN","unverified business particulars"),
    ("Live payment is not yet enabled.","checkout HOLD"),
    ("No information is transmitted in this Release Candidate.","lead form disabled"),
    ("pending explicit human approval","policy effective dates pending"),
]:
    found=any(token in p.read_text() for p in pages)
    if found:
        hold_reasons.append(label)

if errors:
    print("LDS production activation surface contract: FAIL")
    for e in errors:
        print("-",e)
    sys.exit(1)

if not hold_reasons:
    print("LDS production activation surface contract: UNEXPECTED GO")
    print("RC blockers disappeared without an explicit activation-mode contract update")
    sys.exit(1)

print("LDS production activation surface contract: PASS")
print("mode=RC_HOLD")
for r in hold_reasons:
    print("hold:",r)
print("public_indexing=BLOCKED")
