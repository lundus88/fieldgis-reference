-- VL Production Activation Readiness hardening — reverse migration
-- Date: 2026-10-04
-- Use only under explicit human rollback authority.
--
-- This reverse script removes only the functions introduced by the forward migration.
-- It intentionally does NOT:
--   - revert or synthesize public.vl_cert_health data;
--   - delete audit records;
--   - mutate approvals, deployments, factory runs, workflows or certification evidence.
-- If a health finalization has already occurred, data-level disposition requires a
-- separate evidence-backed human decision rather than an automatic timestamp rewrite.

drop function if exists public.authorize_vl_cert_health_finalization(timestamptz,integer,text,text);
drop function if exists private.finalize_vl_cert_health_from_fresh_certification(timestamptz,integer,bigint);
drop function if exists public.get_vl_cert_health_effective(integer);
drop function if exists private.get_effective_vl_cert_health(interval);
drop function if exists public.vl_expire_stale_approval(uuid,text,jsonb,interval);
drop function if exists private.expire_stale_approval(uuid,text,jsonb,interval);
drop function if exists public.vl_reconcile_stale_factory_workflow(uuid,text,text,jsonb,interval);
drop function if exists private.reconcile_stale_factory_workflow(uuid,text,text,jsonb,interval);
