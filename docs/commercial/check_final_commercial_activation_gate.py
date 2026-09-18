#!/usr/bin/env python3
from pathlib import Path
import json, sys

gate_path=Path("docs/commercial/LDS_FINAL_COMMERCIAL_ACTIVATION_GATE.md")
evidence_path=Path("docs/commercial/LDS_BUSINESS_LICENCE_EVIDENCE.json")

text=gate_path.read_text()
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

if not evidence_path.exists():
    errors.append("business/licence evidence manifest missing")
else:
    evidence=json.loads(evidence_path.read_text())
    if evidence.get("schema")!="lds.business-licence-evidence/1":
        errors.append("unexpected licence evidence schema")
    identity=evidence.get("business_identity",{})
    trade=identity.get("trade_name",{})
    if trade.get("value")!="LUNDUS DIGITAL SYSTEMS":
        errors.append("approved trade name drift")
    if trade.get("status")!="verified_from_user_decision":
        errors.append("trade name evidence classification drift")
    licence=evidence.get("licence_gate",{})
    if licence.get("status")!="processing":
        errors.append("licence status must remain processing until official evidence is captured")
    if licence.get("evidence_level")!="user_attested":
        errors.append("licence evidence must remain user_attested until official evidence is captured")
    if licence.get("pass_allowed") is not False:
        errors.append("licence PASS must be blocked while evidence is user-attested only")
    gates=evidence.get("gate_status",{})
    if gates.get("LICENCE_READY")!="HOLD":
        errors.append("LICENCE_READY must remain HOLD")
    if gates.get("LEGAL_TRUST_READY")!="HOLD":
        errors.append("LEGAL_TRUST_READY must remain HOLD")
    missing=[k for k,v in identity.items() if isinstance(v,dict) and v.get("status")=="missing"]
    for key in [
        "registered_legal_entity_name","registration_number","licence_or_approval_number",
        "official_trade_address","official_email","official_phone",
        "final_commercial_domain","support_complaint_channel"
    ]:
        if key not in missing:
            errors.append(f"expected unverified business particular missing from HOLD set: {key}")

if errors:
    print("Final commercial activation gate: FAIL")
    for e in errors:
        print("-",e)
    sys.exit(1)

print("Final commercial activation gate: PASS")
print("licence_evidence=user_attested processing; pass_allowed=false")
