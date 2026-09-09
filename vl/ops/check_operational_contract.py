#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
RECON = (ROOT / "vl/ops/reconciliation_contract.sql").read_text(encoding="utf-8")
HEALTH = (ROOT / "vl/ops/health_freshness_contract.sql").read_text(encoding="utf-8")

required_recon = [
    "private.reconcile_stale_factory_workflow",
    "public.vl_reconcile_stale_factory_workflow",
    "private.expire_stale_approval",
    "public.vl_expire_stale_approval",
    "for update",
    "e.kind='production'",
    "production_locked is distinct from true",
    "manual_review_required",
    "manufactured_success",
    "production_authority_changed",
    "grant execute on function public.vl_reconcile_stale_factory_workflow",
    "grant execute on function public.vl_expire_stale_approval",
    "to service_role",
]
for token in required_recon:
    assert token.lower() in RECON.lower(), f"missing reconciliation safeguard: {token}"

required_health = [
    "private.get_effective_vl_cert_health",
    "public.get_vl_cert_health_effective",
    "v_effective_status := 'stale'",
    "grant execute on function public.get_vl_cert_health_effective",
    "to service_role",
]
for token in required_health:
    assert token.lower() in HEALTH.lower(), f"missing health safeguard: {token}"

# These contracts must never create a positive lifecycle state. Positive states may
# appear in read-only comparisons/comments, but never on the right-hand side of SET.
for forbidden in ("certified", "succeeded", "approved", "deployed", "deploying"):
    pat = re.compile(rf"\bset\s+state\s*=\s*'{forbidden}'", re.I)
    assert not pat.search(RECON), f"forbidden positive state mutation: {forbidden}"

assert not re.search(r"\bupdate\s+public\.deployments\b", RECON, re.I), "deployment mutation is forbidden"
assert not re.search(r"\b(insert|update|delete)\s+(into\s+|from\s+)?public\.vl_cert_health\b", HEALTH, re.I), "health freshness contract must be read-only"

# Public SECURITY DEFINER wrappers must be explicitly removed from ordinary client roles.
for fn in (
    "vl_reconcile_stale_factory_workflow",
    "vl_expire_stale_approval",
):
    assert re.search(rf"revoke all on function public\.{fn}\([^;]+\) from public,anon,authenticated;", RECON, re.I), f"missing revoke for {fn}"
assert re.search(r"revoke all on function public\.get_vl_cert_health_effective\([^;]+\) from public,anon,authenticated;", HEALTH, re.I), "missing health wrapper revoke"

print("VL_OPERATIONAL_RECONCILIATION_CONTRACT=PASS")
