#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT = ROOT / "vl/lom-governance/event-envelope.schema.json"
AUTH = ROOT / "vl/lom-governance/authority-plane-map.json"

def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)

event = json.loads(EVENT.read_text(encoding="utf-8"))
auth = json.loads(AUTH.read_text(encoding="utf-8"))

if event.get("$id") != "lom.event-envelope/1":
    fail("event envelope id mismatch")

required = set(event.get("required") or [])
must = {
    "schema","event_id","event_type","source_component","objective_id",
    "occurred_at","evidence_refs","idempotency_key","risk_class",
    "target_environment","authority_requirement","correlation_id",
    "payload_digest","payload"
}
if required != must:
    fail("canonical event envelope required fields mismatch")

if auth.get("schema") != "lom.authority-plane-map/1":
    fail("authority plane map schema mismatch")
if auth.get("principle") != "authentication != authorization != capability != execution authority":
    fail("authority separation principle mismatch")

layers = {row.get("layer"): row for row in auth.get("layers") or []}
for layer in ("AUTHENTICATION","AUTHORIZATION","CAPABILITY_ELIGIBILITY","ACTION_POLICY","EXECUTION","HUMAN_AUTHORITY"):
    if layer not in layers:
        fail(f"authority layer missing: {layer}")

for layer in ("AUTHENTICATION","AUTHORIZATION","CAPABILITY_ELIGIBILITY","ACTION_POLICY","EXECUTION"):
    if layers[layer].get("may_grant_execution_authority") is not False:
        fail(f"non-human layer widens authority: {layer}")

inv = auth.get("invariants") or {}
for key in (
    "default_deny",
    "production_approval_human_only",
    "authentication_alone_never_authorizes_action",
    "capability_presence_alone_never_authorizes_action",
):
    if inv.get(key) is not True:
        fail(f"authority invariant missing: {key}")
if inv.get("delegation_may_widen_scope") is not False:
    fail("delegation widening invariant broken")

print("LOM_CORE_SYSTEMS_CONSOLIDATION=PASS")
print(f"EVENT_FIELDS={len(required)}")
print(f"AUTHORITY_LAYERS={len(layers)}")
