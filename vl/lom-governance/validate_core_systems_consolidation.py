#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT = ROOT / "vl/lom-governance/event-envelope.schema.json"
AUTH = ROOT / "vl/lom-governance/authority-plane-map.json"
RECON = ROOT / "vl/lom-governance/reconciliation-policy.json"

def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)

event = json.loads(EVENT.read_text(encoding="utf-8"))
auth = json.loads(AUTH.read_text(encoding="utf-8"))
recon = json.loads(RECON.read_text(encoding="utf-8"))

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

if recon.get("schema") != "lom.reconciliation-policy/1":
    fail("reconciliation policy schema mismatch")
retry = recon.get("retry_policy") or {}
for key in (
    "infinite_retry_forbidden",
    "attempt_budget_required",
    "retry_requires_reason",
    "retry_requires_same_or_narrower_authority",
    "retry_requires_idempotency_binding",
):
    if retry.get(key) is not True:
        fail(f"reconciliation retry invariant missing: {key}")
if retry.get("exhausted_attempts_terminal") != "HOLD":
    fail("attempt budget exhaustion must HOLD")

rec = recon.get("reconciliation") or {}
for key in (
    "evidence_refs_required",
    "failure_reason_required",
    "original_event_preserved",
    "original_payload_digest_preserved",
    "replay_requires_remediation_evidence",
    "authority_or_evidence_conflict_requires_human_review",
    "production_replay_requires_human_approval",
    "policy_gate_bypass_forbidden",
):
    if rec.get(key) is not True:
        fail(f"reconciliation invariant missing: {key}")

rinv = recon.get("invariants") or {}
for key in (
    "fail_closed",
    "no_synthetic_pass",
    "no_authority_widening_during_recovery",
    "no_automatic_human_gate_approval",
    "append_only_failure_evidence",
):
    if rinv.get(key) is not True:
        fail(f"reconciliation hard invariant missing: {key}")

print("LOM_CORE_SYSTEMS_CONSOLIDATION=PASS")
print(f"EVENT_FIELDS={len(required)}")
print(f"AUTHORITY_LAYERS={len(layers)}")
print(f"RECON_STATES={len(recon.get('states') or [])}")
