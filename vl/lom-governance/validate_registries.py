#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "vl/lom-governance/capability-registry.json"
KNOW = ROOT / "vl/lom-knowledge-foundation/master-knowledge-registry.json"

VALID_STATUS = {"EXISTING","PARTIAL","MISSING","DUPLICATE","BLOCKED"}
VALID_AUTH = {
    "AUTHORITATIVE_OFFICIAL","PROFESSIONAL_REFERENCE","TECHNICAL_REFERENCE",
    "PROJECT_EVIDENCE","GENERATED_MATERIAL","ARCHIVE"
}

def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)

cap = json.loads(CAP.read_text(encoding="utf-8"))
know = json.loads(KNOW.read_text(encoding="utf-8"))

if cap.get("policy") != "one capability -> one authoritative owner -> many consumers":
    fail("anti-duplication policy mismatch")
if cap.get("duplicate_rule") != "REUSE_EXTEND_INTEGRATE_BEFORE_BUILD":
    fail("reuse-first rule missing")

ids=set()
owners={}
for row in cap.get("capabilities", []):
    cid=row.get("id")
    if not cid or cid in ids:
        fail(f"duplicate or missing capability id: {cid}")
    ids.add(cid)
    if row.get("status") not in VALID_STATUS:
        fail(f"invalid capability status for {cid}")
    owner=row.get("owner")
    if not owner:
        fail(f"missing owner for {cid}")
    owners.setdefault(owner, []).append(cid)

required = set(know.get("required_fields", []))
if know.get("owner") != "LOM Knowledge Librarian":
    fail("knowledge librarian owner missing")
if know.get("duplicate_policy") != "FLAG_ONLY_NO_AUTODELETE":
    fail("knowledge duplicate policy is unsafe")
if know.get("low_confidence_policy") != "FAIL_CLOSED":
    fail("knowledge confidence policy is not fail-closed")
if set(know.get("classification", [])) != VALID_AUTH:
    fail("knowledge classifications mismatch")
for i,row in enumerate(know.get("records", [])):
    missing=required-set(row)
    if missing:
        fail(f"knowledge record {i} missing fields: {sorted(missing)}")
    if row.get("authority_level") not in VALID_AUTH:
        fail(f"knowledge record {i} has invalid authority")
    conf=row.get("confidence")
    if not isinstance(conf,(int,float)) or not 0 <= conf <= 1:
        fail(f"knowledge record {i} confidence must be 0..1")

print("LOM_REGISTRY_VALIDATION=PASS")
print(f"CAPABILITIES={len(ids)}")
print(f"KNOWLEDGE_RECORDS={len(know.get('records', []))}")
