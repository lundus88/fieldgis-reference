#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "vl/lom-governance/capability-registry.json"
KNOW = ROOT / "vl/lom-knowledge-foundation/master-knowledge-registry.json"
DOCTRINE = ROOT / "vl/lom-governance/core-values-doctrine.json"
HVAE = ROOT / "vl/lom-governance/high-value-absorption-policy.json"

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
doctrine = json.loads(DOCTRINE.read_text(encoding="utf-8"))
hvae = json.loads(HVAE.read_text(encoding="utf-8"))

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
    if not (ROOT / owner).exists():
        fail(f"owner target does not exist for {cid}: {owner}")
    owners.setdefault(owner, []).append(cid)

specialists=cap.get("specialist_on_demand") or {}
if specialists.get("policy") != "LOAD_ONLY_WHEN_DOMAIN_NEEDS_IT":
    fail("specialist-on-demand policy missing")
if specialists.get("human_authority_preserved") is not True:
    fail("specialist policy weakens human authority")
hr=cap.get("hr_policy") or {}
if hr.get("mode") != "HR_ADAPTER_PLUS_SPECIALIST_HRMS":
    fail("HR adapter policy missing")
if hr.get("duplicate_payroll_attendance_leave_engine_forbidden") is not True:
    fail("duplicate HR engine prohibition missing")

vps = next((row for row in cap.get("capabilities", []) if row.get("id") == "vps_execution"), None)
if not vps:
    fail("vps execution capability missing")
if vps.get("status") != "EXISTING":
    fail("verified VPS execution capability must be EXISTING")
if vps.get("activation_state") != "LIVE_VERIFIED_NON_PRODUCTION":
    fail("VPS activation state mismatch")
if vps.get("activation_evidence_verified") is not True or vps.get("live_vps_verified") is not True:
    fail("VPS live verification evidence missing")
if vps.get("secure_ingress_verified") is not True:
    fail("VPS secure ingress verification missing")
if vps.get("reboot_recovery_verified") is not True:
    fail("VPS reboot recovery verification missing")
if vps.get("operational_probe_verified") is not True:
    fail("VPS operational probe verification missing")
if vps.get("production_authority") != "HUMAN_ONLY":
    fail("VPS Production authority must remain HUMAN_ONLY")
if vps.get("activation_boundary") != "NON_PRODUCTION_ONLY":
    fail("VPS activation boundary widened")
if "blocker" in vps:
    fail("resolved VPS blocker must not remain canonical")
if vps.get("runtime_host_policy") != "VPS_ONLY":
    fail("VPS-only runtime policy missing")
if vps.get("canonical_runtime_node") != "v103067":
    fail("canonical VPS runtime node mismatch")
if vps.get("office_workstation_role") != "EXCLUDED_FROM_RUNTIME":
    fail("office workstation must be excluded from LOM runtime")
if vps.get("fallback_to_office_workstation") != "FORBIDDEN":
    fail("office workstation fallback must remain forbidden")
excluded = set(vps.get("excluded_operational_dependencies") or [])
if {"OFFICE_WORKSTATION"} - excluded:
    fail("office workstation exclusion missing")

if doctrine.get("schema") != "lom.core-values-doctrine/1":
    fail("core values doctrine schema mismatch")
principles = doctrine.get("principles") or []
principle_ids = {p.get("id") for p in principles}
required_principles = {
    "evidence_before_action",
    "reversible_by_default",
    "fail_closed_recover_gracefully",
    "single_source_of_truth",
    "provenance_everywhere",
    "capability_before_autonomy",
    "measure_before_scale",
    "economic_intelligence",
    "independent_verification",
    "institutional_memory",
    "compress_time_to_outcome",
    "speed_without_quality_debt",
    "outcome_over_artifact",
    "productize_repeatable_customize_valuable",
    "customer_sovereignty_portability",
    "continuous_competitive_adaptation",
}
if principle_ids != required_principles:
    fail("core values doctrine principles mismatch")
compass = doctrine.get("outcome_compass") or {}
if compass.get("north_star") != "Compress Time-to-Outcome without compromising trust, quality, evidence or human authority.":
    fail("outcome compass north star mismatch")
if compass.get("optimization_order") != ["SAFE","USEFUL","FAST","MEASURABLE","REPEATABLE","SCALABLE","SELF_IMPROVING"]:
    fail("outcome compass optimization order mismatch")

hard = doctrine.get("hard_invariants") or {}
for key in (
    "human_authority_preserved",
    "production_change_requires_human_gate",
    "authority_widening_requires_human_gate",
    "financial_legal_customer_commitments_require_human_gate",
    "vendor_neutral_core",
    "duplicate_core_capability_forbidden_without_proven_gap",
):
    if hard.get(key) is not True:
        fail(f"core doctrine hard invariant missing: {key}")

if hvae.get("schema") != "lom.high-value-absorption-policy/1":
    fail("HVAE schema mismatch")
if hvae.get("owner") != "vl/lom-governance":
    fail("HVAE owner mismatch")
if hvae.get("principle") != "Novel != Valuable. Valuable != Necessary. Necessary != New Module.":
    fail("HVAE principle mismatch")
if (hvae.get("autonomy") or {}).get("ceiling") != "PREPARE_PR":
    fail("HVAE autonomy ceiling widened")
if (hvae.get("autonomy") or {}).get("production_authority") != "HUMAN_ONLY":
    fail("HVAE production authority must remain HUMAN_ONLY")
if (hvae.get("autonomy") or {}).get("self_approval") != "FORBIDDEN":
    fail("HVAE self approval must remain forbidden")
if (hvae.get("autonomy") or {}).get("automatic_module_creation") != "FORBIDDEN":
    fail("HVAE automatic module creation must remain forbidden")
if hvae.get("reuse_order") != ["REUSE","EXTEND","INTEGRATE","BUILD_ONLY_ON_PROVEN_GAP"]:
    fail("HVAE reuse-first order mismatch")
required_hvae = {
    "evidence_present",
    "owner_identified",
    "duplicate_scan_complete",
    "architecture_target_identified",
    "risk_assessed",
    "rollback_defined_for_runtime_change",
}
if set(hvae.get("mandatory_checks", [])) != required_hvae:
    fail("HVAE mandatory checks mismatch")

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
print(f"CORE_VALUES={len(principles)}")
print(f"HVAE_DISPOSITIONS={len(hvae.get('dispositions', []))}")
