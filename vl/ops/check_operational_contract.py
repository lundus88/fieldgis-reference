#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
RECON = (ROOT / "vl/ops/reconciliation_contract.sql").read_text(encoding="utf-8")
HEALTH = (ROOT / "vl/ops/health_freshness_contract.sql").read_text(encoding="utf-8")
WRITER = (ROOT / "vl/ops/cert_health_writer_contract.sql").read_text(encoding="utf-8")

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

required_writer = [
    "private.finalize_vl_cert_health_from_fresh_certification",
    "p_run_started_at timestamptz",
    "p_max_run_age_seconds integer",
    "p_human_authorization_ref text",
    "p_max_run_age_seconds < 60",
    "p_max_run_age_seconds > 86400",
    "r.status='active'",
    "p.status='active'",
    "r2.evaluated_at >= p_run_started_at",
    "e.created_at >= p_run_started_at",
    "e.evidence_status='pass'",
    "e.source_uri is not null",
    "f.target_environment='staging'",
    "f.production_locked is true",
    "f.state='awaiting_approval'",
    "having count(distinct e.evidence_type)=a.required_count",
    "cr.decision <> 'certified'",
    "cr.score < a.minimum_score",
    "cr.distinct_run_count < a.minimum_distinct_runs",
    "FRESH_CERTIFICATION_INCOMPLETE",
    "RUN_WINDOW_STALE",
    "ACTIVE_BUILDER_POLICY_MISMATCH",
    "vl.cert_health_finalization_blocked",
    "vl.cert_health_finalized",
    "human_authorization_ref",
    "update public.vl_cert_health",
    "where id=1",
    "get diagnostics v_updated = row_count",
    "grant execute on function private.finalize_vl_cert_health_from_fresh_certification",
    "to service_role",
]
for token in required_writer:
    assert token.lower() in WRITER.lower(), f"missing cert-health writer safeguard: {token}"

# Reconciliation contracts must never create a positive lifecycle state.
for forbidden in ("certified", "succeeded", "approved", "deployed", "deploying"):
    pat = re.compile(rf"\bset\s+state\s*=\s*'{forbidden}'", re.I)
    assert not pat.search(RECON), f"forbidden positive state mutation: {forbidden}"

assert not re.search(r"\bupdate\s+public\.deployments\b", RECON, re.I), "deployment mutation is forbidden"
assert not re.search(
    r"\b(insert|update|delete)\s+(into\s+|from\s+)?public\.vl_cert_health\b",
    HEALTH,
    re.I,
), "health freshness contract must be read-only"

# Certification-health finalizer is allowed to update exactly the one existing health row,
# but it must not manufacture certification evidence/results or mutate lifecycle authority.
for pattern, message in [
    (r"\binsert\s+into\s+public\.builder_certification_evidence\b", "writer must not manufacture certification evidence"),
    (r"\bupdate\s+public\.builder_certification_evidence\b", "writer must not modify certification evidence"),
    (r"\binsert\s+into\s+public\.builder_certification_results\b", "writer must not manufacture certification results"),
    (r"\bupdate\s+public\.builder_certification_results\b", "writer must not modify certification results"),
    (r"\bupdate\s+public\.factory_runs\b", "writer must not mutate factory runs"),
    (r"\bupdate\s+public\.deployments\b", "writer must not mutate deployments"),
    (r"\bupdate\s+public\.approvals\b", "writer must not mutate approvals"),
    (r"\bupdate\s+public\.builder_registry\b", "writer must not activate builders"),
    (r"\bupdate\s+public\.release_gates\b", "writer must not mutate release gates"),
    (r"\binsert\s+into\s+public\.vl_cert_health\b", "writer must not bootstrap a missing health row"),
]:
    assert not re.search(pattern, WRITER, re.I), message

health_updates = re.findall(r"(?im)^\\s*update\\s+public\\.vl_cert_health\\b", WRITER)
assert len(health_updates) == 1, f"expected one guarded health update, found {len(health_updates)}"

assert not re.search(r"\bset\s+production_locked\s*=\s*false\b", WRITER, re.I), "writer must never unlock production"
assert not re.search(r"\bset\s+status\s*=\s*'active'\b", WRITER, re.I), "writer must never activate a builder"
assert "source_run_id, source_uri and human_authorization_ref are required" in WRITER
assert "expected exactly one vl_cert_health row" in WRITER

# Public SECURITY DEFINER wrappers must be explicitly removed from ordinary client roles.
for fn in (
    "vl_reconcile_stale_factory_workflow",
    "vl_expire_stale_approval",
):
    assert re.search(
        rf"revoke all on function public\.{fn}\([^;]+\) from public,anon,authenticated;",
        RECON,
        re.I,
    ), f"missing revoke for {fn}"

assert re.search(
    r"revoke all on function public\.get_vl_cert_health_effective\([^;]+\) from public,anon,authenticated;",
    HEALTH,
    re.I,
), "missing health wrapper revoke"

assert re.search(
    r"revoke all on function private\.finalize_vl_cert_health_from_fresh_certification\([\s\S]+?\) from public,anon,authenticated;",
    WRITER,
    re.I,
), "missing cert-health writer revoke"

print("VL_OPERATIONAL_RECONCILIATION_CONTRACT=PASS")
