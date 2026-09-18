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
  "GOLDEN_TRANSACTION_DRY_RUN: PASS",
  "GOLDEN_TRANSACTION_PASS: HOLD",
  "PREVIEW_EXECUTION: HOLD / blocked_by_tooling_and_auth_path",
  "LIVE_LEAD_INTAKE: HOLD",
  "PUBLIC_PAYMENT_ACTIVATION: HOLD",
  "PUBLIC_LAUNCH: HOLD",
  "Do not bypass repository rulesets.",
  "A browser redirect is not payment evidence.",
  "A dry-run PASS is not a live Golden Transaction PASS.",
  "This document does not authorize:",
  "Production deployment",
  "live billing activation",
  "live customer charging",
]
for token in required:
    if token not in text:
        errors.append(f"missing guardrail: {token}")

merged_prs={
  "#277":"807b588dddd4bd1fd2c0c24e9b247a73ca895514",
  "#275":"af2673d1b9567b1aefed1877c3fc9b8b0419758c",
  "#276":"8ffacb6b78d4107a4906d7960b3f048dfac8e2d9",
  "#278":"bef77304464b9e6480191090d8f7672ce203aad4",
  "#280":"d1fb85f69fe697848a8e654017d4b680bdb0b8ee",
  "#281":"732bb7e2da9418ba9b74c08704bb3d3f033af6fe",
  "#279":"724d293ecbd06ec191157d18ac3abb5a1fdcb2ff",
  "#283":"e2d52171503bd725c3638f0ac2fb60fe6d2e564e",
  "#284":"54530abc410cfccb1f5ea3219ec4ac79b4ee1901",
  "#285":"7a544c808b6e76491cc6ee50d8983fa35aa04316",
  "#286":"bc8273a27d74dc489b2081aa2c62784d3673c799",
}
for pr,sha in merged_prs.items():
    if pr not in text or sha not in text:
        errors.append(f"missing merged evidence for {pr}")

stale_tokens=[
  "Merge #277 first.",
  "protected-main merge pending",
  "PR #275-#282 and LundusLead #151 still require normal repository review/merge gates",
]
for token in stale_tokens:
    if token in text:
        errors.append(f"stale activation state remains: {token}")

sequence=[
  "Refresh PR #282 against current `main`",
  "Resolve LundusLead PR #151",
  "Verify official business/licence evidence",
  "Establish a safe dedicated Preview",
  "Run integration checks:",
  "perform one explicitly authorized controlled paid Commercial Golden Transaction",
  "Only then consider public payment activation",
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
print("protected_main_sequence=merged through #286; #282 remains human-gated")
print("licence_evidence=user_attested processing; pass_allowed=false")
print("production_activation=HOLD")
