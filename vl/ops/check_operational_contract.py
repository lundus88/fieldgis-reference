#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
RECON = (ROOT / "vl/ops/reconciliation_contract.sql").read_text(encoding="utf-8")
HEALTH = (ROOT / "vl/ops/health_freshness_contract.sql").read_text(encoding="utf-8")
WRITER = (ROOT / "vl/ops/cert_health_writer_contract.sql").read_text(encoding="utf-8")
FORWARD = (ROOT / "vl/migrations/20261004154500_cert_health_activation_hardening.sql").read_text(encoding="utf-8")
REVERSE = (ROOT / "vl/ops/rollback_cert_health_activation_20261004.sql").read_text(encoding="utf-8")

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
    "public.authorize_vl_cert_health_finalization",
    "auth.uid()",
    "auth.jwt()->>'aal'",
    "AAL2 MFA required for certification-health authorization",
    "owner/admin membership required",
    "authorization reason must be explicit",
    "evidence_digest must be a lowercase SHA-256 hex digest",
    "production_authority_created",
    "grant execute on function public.authorize_vl_cert_health_finalization",
    "to authenticated",
    "private.finalize_vl_cert_health_from_fresh_certification",
    "p_run_started_at timestamptz",
    "p_max_run_age_seconds integer",
    "p_authorization_audit_id bigint",
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
    "SELECTED_EVIDENCE_RUN_HAS_PRODUCTION_AUTHORITY",
    "EVIDENCE_TOO_OLD_FOR_EFFECTIVE_HEALTH",
    "v_effective_health_window_seconds integer := 1800",
    "d.status in ('approved','deploying','deployed')",
    "d.approved_by is not null",
    "d.deployed_at is not null",
    "vl.cert_health_finalization_blocked",
    "vl.cert_health_finalized",
    "authorization_audit_id",
    "vl.cert_health_finalization_authorized",
    "authenticator_assurance_level",
    "evidence_digest",
    "AUTHORIZATION_NOT_FOUND",
    "AUTHORIZATION_RECORD_INVALID",
    "AUTHORIZATION_AAL2_REQUIRED",
    "AUTHORIZATION_EVIDENCE_DIGEST_MISMATCH",
    "AUTHORIZATION_RUN_BINDING_MISMATCH",
    "AUTHORIZATION_PREDATES_EVIDENCE",
    "AUTHORIZATION_STALE",
    "AUTHORIZATION_SCOPE_MISMATCH",
    "AUTHORIZATION_REPLAYED",
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

health_updates = re.findall(r"(?im)^\s*update\s+public\.vl_cert_health\b", WRITER)
assert len(health_updates) == 1, f"expected one guarded health update, found {len(health_updates)}"

assert not re.search(r"\bset\s+production_locked\s*=\s*false\b", WRITER, re.I), "writer must never unlock production"
assert not re.search(r"\bset\s+status\s*=\s*'active'\b", WRITER, re.I), "writer must never activate a builder"
assert "authorization_audit_id is required" in WRITER
assert "extensions.digest" in WRITER
assert "insert into public.audit_logs(" in WRITER
assert "authorization_scope','FINALIZER_REVALIDATES_ALL_SELECTED_PROJECTS'" in WRITER
assert "created_at >= v_now - interval '15 minutes'" in WRITER
assert "set search_path=''" in WRITER
assert "updated_at=v_health_evidence_at" in WRITER
assert "created_at < v_now - interval '15 minutes'" in WRITER
assert "pm.role in ('owner','admin')" in WRITER
assert "metadata->>'authorization_audit_id'=p_authorization_audit_id::text" in WRITER
assert "expected exactly one vl_cert_health row" in WRITER

# Forward migration must materialize the exact reviewed contracts without hidden drift.
for source, label in (
    (RECON, "reconciliation contract"),
    (HEALTH, "health freshness contract"),
    (WRITER, "certification-health writer contract"),
):
    assert source.strip() in FORWARD, f"forward migration drifted from {label}"

assert "merge does NOT authorize Production deployment" in FORWARD
assert "DDL only" in FORWARD
assert not re.search(r"\binsert\s+into\s+public\.vl_cert_health\b", FORWARD, re.I)
assert not re.search(r"\bupdate\s+public\.vl_cert_health\b", FORWARD.split(WRITER, 1)[0], re.I)

# Reverse migration is code-only rollback. It may drop the introduced functions,
# but must not rewrite evidence, health or lifecycle data.
required_reverse = [
    "drop function if exists public.authorize_vl_cert_health_finalization",
    "drop function if exists private.finalize_vl_cert_health_from_fresh_certification",
    "drop function if exists public.get_vl_cert_health_effective",
    "drop function if exists private.get_effective_vl_cert_health",
    "drop function if exists public.vl_expire_stale_approval",
    "drop function if exists private.expire_stale_approval",
    "drop function if exists public.vl_reconcile_stale_factory_workflow",
    "drop function if exists private.reconcile_stale_factory_workflow",
]
for token in required_reverse:
    assert token.lower() in REVERSE.lower(), f"missing reverse migration function drop: {token}"

reverse_exec = re.sub(r"(?m)^\s*--.*$", "", REVERSE)
for pattern, message in [
    (r"\bupdate\b", "reverse migration must not update data"),
    (r"\binsert\b", "reverse migration must not insert data"),
    (r"\bdelete\b", "reverse migration must not delete data"),
    (r"\btruncate\b", "reverse migration must not truncate data"),
    (r"\bdrop\s+table\b", "reverse migration must not drop tables"),
    (r"\bdrop\s+schema\b", "reverse migration must not drop schemas"),
]:
    assert not re.search(pattern, reverse_exec, re.I), message

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

assert re.search(
    r"revoke all on function public\.authorize_vl_cert_health_finalization\([\s\S]+?\) from public,anon,authenticated,service_role;",
    WRITER,
    re.I,
), "missing authorization producer revoke"

assert re.search(
    r"grant execute on function public\.authorize_vl_cert_health_finalization\([\s\S]+?\) to authenticated;",
    WRITER,
    re.I,
), "authorization producer must be human authenticated only"

# The authorization producer may only write audit intent. It must never mutate
# certification evidence, lifecycle state, deployment state or health state.
producer = WRITER.split(
    "create or replace function public.authorize_vl_cert_health_finalization",
    1,
)[1].split(
    "create or replace function private.finalize_vl_cert_health_from_fresh_certification",
    1,
)[0]
for pattern, message in [
    (r"\bupdate\s+public\.vl_cert_health\b", "authorization producer must not update health"),
    (r"\bupdate\s+public\.factory_runs\b", "authorization producer must not mutate factory runs"),
    (r"\bupdate\s+public\.deployments\b", "authorization producer must not mutate deployments"),
    (r"\bupdate\s+public\.approvals\b", "authorization producer must not mutate approvals"),
    (r"\binsert\s+into\s+public\.builder_certification_evidence\b", "authorization producer must not create evidence"),
    (r"\binsert\s+into\s+public\.builder_certification_results\b", "authorization producer must not create results"),
]:
    assert not re.search(pattern, producer, re.I), message

print("VL_OPERATIONAL_RECONCILIATION_CONTRACT=PASS")
