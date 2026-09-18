#!/usr/bin/env python3
from pathlib import Path
import sys

p=Path("docs/commercial/LDS_FINAL_COMMERCIAL_ACTIVATION_GATE.md")
text=p.read_text()
errors=[]

required=[
  "Overall status: HOLD",
  "OFFER_LOCKED: PASS",
  "LICENCE_READY: HOLD",
  "LEGAL_TRUST_READY: HOLD",
  "GOLDEN_TRANSACTION_PASS: HOLD",
  "Do not bypass repository rulesets.",
  "A browser redirect is not payment evidence.",
  "This document does not authorize:",
  "Production deployment",
  "live billing activation",
  "live customer charging",
]
for token in required:
    if token not in text:
        errors.append(f"missing guardrail: {token}")

sequence=[
  "Merge #277 first.",
  "Run integration checks:",
  "Perform one controlled paid Golden Transaction.",
  "Only then consider public payment activation.",
]
pos=-1
for token in sequence:
    cur=text.find(token)
    if cur<0:
        errors.append(f"missing activation step: {token}")
    elif cur<=pos:
        errors.append(f"activation sequence out of order at: {token}")
    pos=cur

if errors:
    print("Final commercial activation gate: FAIL")
    for e in errors:
        print("-",e)
    sys.exit(1)

print("Final commercial activation gate: PASS")
