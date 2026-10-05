-- VL Production Activation Readiness hardening — forward-only candidate migration
-- Date: 2026-10-04
-- Authority: repository candidate only; merge does NOT authorize Production deployment.
-- Scope: existing operational reconciliation + health freshness + evidence-bound
-- certification-health human authorization/finalization contracts.
-- Data policy: DDL only. No health refresh, approval, deployment, certification evidence,
-- builder activation, or lifecycle state mutation is performed by applying this migration.

-- VL operational reconciliation contract (candidate SQL; NOT auto-deployed)
--
-- Purpose:
--   1. Reconcile historical factory/workflow state mismatches toward safe terminal states.
--   2. Allow explicit, governed expiry of stale pending approvals.
--   3. Never manufacture success/certification/approval/deployment evidence.
--
-- Deployment governance:
--   - Review and test on an isolated Supabase development branch before promotion.
--   - Do not execute this file directly against production as an ad-hoc cleanup.
--   - Production authority, promoter rules and human approval rules remain unchanged.

create or replace function private.reconcile_stale_factory_workflow(
  p_factory_run_id uuid,
  p_disposition text,
  p_reason text,
  p_runner_identity jsonb,
  p_min_age interval default interval '24 hours'
)
returns jsonb
language plpgsql
security definer
set search_path=private,public,pg_temp
as $$
declare
  v_run public.factory_runs%rowtype;
  v_workflow public.workflows%rowtype;
  v_project public.projects%rowtype;
  v_age interval;
  v_event_type text := 'governed_historical_reconciliation';
begin
  if p_factory_run_id is null then
    raise exception 'factory_run_id required' using errcode='22023';
  end if;
  if coalesce(trim(p_reason),'') = '' then
    raise exception 'reconciliation reason required' using errcode='22023';
  end if;
  if p_min_age < interval '1 hour' then
    raise exception 'minimum reconciliation age must be at least one hour' using errcode='22023';
  end if;
  if coalesce(p_runner_identity->>'repository','') <> 'lundus88/fieldgis-reference' then
    raise exception 'authorized repository identity required' using errcode='42501';
  end if;

  select * into v_run
  from public.factory_runs
  where id=p_factory_run_id
  for update;
  if not found then
    raise exception 'factory run not found' using errcode='P0002';
  end if;

  select * into v_project from public.projects where id=v_run.project_id;

  if v_run.workflow_id is null then
    raise exception 'factory run has no workflow binding' using errcode='P0001';
  end if;

  select * into v_workflow
  from public.workflows
  where id=v_run.workflow_id
  for update;
  if not found then
    raise exception 'workflow not found' using errcode='P0002';
  end if;

  if v_workflow.project_id is distinct from v_run.project_id then
    raise exception 'project/workflow identity mismatch' using errcode='P0001';
  end if;

  if v_run.target_environment = 'production' or v_run.production_locked is distinct from true then
    raise exception 'production or unlocked factory run cannot be reconciled by historical cleanup' using errcode='42501';
  end if;

  if exists (
    select 1
    from public.deployments d
    join public.environments e on e.id=d.environment_id
    where d.factory_run_id=v_run.id
      and e.kind='production'
  ) then
    raise exception 'factory run has production-environment deployment evidence; manual audit required' using errcode='42501';
  end if;

  v_age := now() - coalesce(v_run.started_at,v_run.created_at);
  if v_age < p_min_age then
    return jsonb_build_object(
      'decision','blocked_not_stale',
      'factory_run_id',v_run.id,
      'factory_state',v_run.state,
      'workflow_state',v_workflow.state,
      'age_seconds',extract(epoch from v_age)::bigint
    );
  end if;

  if (v_run.state='failed' and v_workflow.state='failed')
     or (v_run.state='cancelled' and v_workflow.state='cancelled')
     or (v_run.state='certified' and v_workflow.state='succeeded') then
    return jsonb_build_object(
      'decision','already_consistent',
      'factory_run_id',v_run.id,
      'factory_state',v_run.state,
      'workflow_state',v_workflow.state
    );
  end if;

  if v_run.state='failed' and v_workflow.state='running' then
    if p_disposition <> 'align_failed' then
      raise exception 'failed factory run requires align_failed disposition' using errcode='22023';
    end if;

    update public.workflows
    set state='failed',
        finished_at=coalesce(finished_at,now()),
        output=coalesce(output,'{}'::jsonb) || jsonb_build_object(
          'historical_reconciliation',jsonb_build_object(
            'factory_run_id',v_run.id,
            'reason',p_reason,
            'at',now(),
            'runner_identity',p_runner_identity,
            'manufactured_success',false,
            'production_authority_changed',false
          )
        )
    where id=v_workflow.id;

    insert into private.factory_execution_events(
      factory_run_id,project_id,event_type,from_state,to_state,payload
    ) values (
      v_run.id,v_run.project_id,v_event_type,
      v_workflow.state,'failed',
      jsonb_build_object(
        'workflow_id',v_workflow.id,
        'project_name',v_project.name,
        'disposition',p_disposition,
        'reason',p_reason,
        'runner_identity',p_runner_identity,
        'factory_state_unchanged',v_run.state,
        'production_authority_changed',false
      )
    );

    return jsonb_build_object(
      'decision','reconciled',
      'factory_run_id',v_run.id,
      'factory_state','failed',
      'workflow_state','failed'
    );
  end if;

  if v_run.state='validating' and v_workflow.state='running' then
    if p_disposition <> 'cancel_incomplete' then
      raise exception 'validating orphan requires cancel_incomplete disposition' using errcode='22023';
    end if;

    update public.factory_runs
    set state='cancelled',
        finished_at=coalesce(finished_at,now()),
        error_text=coalesce(error_text,'Governed historical reconciliation: incomplete lifecycle cancelled')
    where id=v_run.id;

    update public.workflows
    set state='cancelled',
        finished_at=coalesce(finished_at,now()),
        output=coalesce(output,'{}'::jsonb) || jsonb_build_object(
          'historical_reconciliation',jsonb_build_object(
            'factory_run_id',v_run.id,
            'reason',p_reason,
            'at',now(),
            'runner_identity',p_runner_identity,
            'manufactured_success',false,
            'production_authority_changed',false
          )
        )
    where id=v_workflow.id;

    insert into private.factory_execution_events(
      factory_run_id,project_id,event_type,from_state,to_state,payload
    ) values (
      v_run.id,v_run.project_id,v_event_type,
      'validating','cancelled',
      jsonb_build_object(
        'workflow_id',v_workflow.id,
        'workflow_from_state',v_workflow.state,
        'workflow_to_state','cancelled',
        'project_name',v_project.name,
        'disposition',p_disposition,
        'reason',p_reason,
        'runner_identity',p_runner_identity,
        'manufactured_success',false,
        'production_authority_changed',false
      )
    );

    return jsonb_build_object(
      'decision','reconciled',
      'factory_run_id',v_run.id,
      'factory_state','cancelled',
      'workflow_state','cancelled'
    );
  end if;

  return jsonb_build_object(
    'decision','manual_review_required',
    'factory_run_id',v_run.id,
    'factory_state',v_run.state,
    'workflow_state',v_workflow.state,
    'reason','state pair is outside the narrowly authorized historical reconciliation matrix'
  );
end;
$$;

revoke all on function private.reconcile_stale_factory_workflow(uuid,text,text,jsonb,interval) from public,anon,authenticated;

create or replace function public.vl_reconcile_stale_factory_workflow(
  p_factory_run_id uuid,
  p_disposition text,
  p_reason text,
  p_runner_identity jsonb,
  p_min_age interval default interval '24 hours'
)
returns jsonb
language sql
security definer
set search_path=private,public,pg_temp
as $$
  select private.reconcile_stale_factory_workflow(
    p_factory_run_id,p_disposition,p_reason,p_runner_identity,p_min_age
  );
$$;

revoke all on function public.vl_reconcile_stale_factory_workflow(uuid,text,text,jsonb,interval) from public,anon,authenticated;
grant execute on function public.vl_reconcile_stale_factory_workflow(uuid,text,text,jsonb,interval) to service_role;

create or replace function private.expire_stale_approval(
  p_approval_id uuid,
  p_reason text,
  p_runner_identity jsonb,
  p_min_age interval default interval '7 days'
)
returns jsonb
language plpgsql
security definer
set search_path=private,public,pg_temp
as $$
declare
  v_approval public.approvals%rowtype;
  v_run public.factory_runs%rowtype;
  v_workflow public.workflows%rowtype;
  v_age interval;
begin
  if p_approval_id is null then
    raise exception 'approval_id required' using errcode='22023';
  end if;
  if coalesce(trim(p_reason),'') = '' then
    raise exception 'expiry reason required' using errcode='22023';
  end if;
  if p_min_age < interval '24 hours' then
    raise exception 'minimum approval age must be at least 24 hours' using errcode='22023';
  end if;
  if coalesce(p_runner_identity->>'repository','') <> 'lundus88/fieldgis-reference' then
    raise exception 'authorized repository identity required' using errcode='42501';
  end if;

  select * into v_approval
  from public.approvals
  where id=p_approval_id
  for update;
  if not found then
    raise exception 'approval not found' using errcode='P0002';
  end if;

  if v_approval.status <> 'pending' then
    return jsonb_build_object('decision','already_disposed','approval_id',v_approval.id,'status',v_approval.status);
  end if;

  v_age := now() - v_approval.requested_at;
  if v_age < p_min_age then
    return jsonb_build_object('decision','blocked_not_stale','approval_id',v_approval.id,'age_seconds',extract(epoch from v_age)::bigint);
  end if;

  if v_approval.factory_run_id is null then
    raise exception 'pending approval is not factory-run bound; manual review required' using errcode='P0001';
  end if;

  select * into v_run from public.factory_runs where id=v_approval.factory_run_id for update;
  if not found then
    raise exception 'factory run not found for approval' using errcode='P0002';
  end if;

  if v_run.target_environment='production' or v_run.production_locked is distinct from true then
    raise exception 'production or unlocked approval cannot be expired by stale-cleanup path' using errcode='42501';
  end if;

  if exists (
    select 1
    from public.deployments d
    join public.environments e on e.id=d.environment_id
    where d.factory_run_id=v_run.id
      and e.kind='production'
  ) then
    raise exception 'approval has production-environment deployment evidence; manual audit required' using errcode='42501';
  end if;

  if v_run.workflow_id is null or v_run.workflow_id is distinct from v_approval.workflow_id then
    raise exception 'approval/factory/workflow identity mismatch' using errcode='P0001';
  end if;

  select * into v_workflow from public.workflows where id=v_run.workflow_id for update;
  if not found then
    raise exception 'workflow not found for approval' using errcode='P0002';
  end if;

  if v_run.state <> 'awaiting_approval' or v_workflow.state <> 'waiting_approval' then
    raise exception 'stale approval state pair is not eligible for governed expiry' using errcode='P0001';
  end if;

  update public.approvals
  set status='expired',
      decided_at=now(),
      rationale=concat_ws(E'\n',nullif(rationale,''),'Expired by governed stale-approval disposition: ' || p_reason)
  where id=v_approval.id;

  update public.factory_runs
  set state='cancelled',
      finished_at=coalesce(finished_at,now()),
      error_text=coalesce(error_text,'Governed approval expiry: human approval window elapsed')
  where id=v_run.id;

  update public.workflows
  set state='cancelled',
      finished_at=coalesce(finished_at,now()),
      output=coalesce(output,'{}'::jsonb) || jsonb_build_object(
        'approval_expiry',jsonb_build_object(
          'approval_id',v_approval.id,
          'reason',p_reason,
          'at',now(),
          'runner_identity',p_runner_identity,
          'production_authority_changed',false
        )
      )
  where id=v_workflow.id;

  insert into private.factory_execution_events(
    factory_run_id,project_id,event_type,from_state,to_state,payload
  ) values (
    v_run.id,v_run.project_id,'governed_approval_expiry',
    'awaiting_approval','cancelled',
    jsonb_build_object(
      'approval_id',v_approval.id,
      'workflow_id',v_workflow.id,
      'reason',p_reason,
      'runner_identity',p_runner_identity,
      'approval_status','expired',
      'production_authority_changed',false
    )
  );

  return jsonb_build_object(
    'decision','expired',
    'approval_id',v_approval.id,
    'factory_run_id',v_run.id,
    'factory_state','cancelled',
    'workflow_state','cancelled',
    'production_authority_changed',false
  );
end;
$$;

revoke all on function private.expire_stale_approval(uuid,text,jsonb,interval) from public,anon,authenticated;

create or replace function public.vl_expire_stale_approval(
  p_approval_id uuid,
  p_reason text,
  p_runner_identity jsonb,
  p_min_age interval default interval '7 days'
)
returns jsonb
language sql
security definer
set search_path=private,public,pg_temp
as $$
  select private.expire_stale_approval(p_approval_id,p_reason,p_runner_identity,p_min_age);
$$;

revoke all on function public.vl_expire_stale_approval(uuid,text,jsonb,interval) from public,anon,authenticated;
grant execute on function public.vl_expire_stale_approval(uuid,text,jsonb,interval) to service_role;


-- VL certification health freshness contract (candidate SQL; NOT auto-deployed)
--
-- The current public.vl_cert_health row can report status='ok' indefinitely even when
-- updated_at is stale. This contract makes staleness explicit and fail-closed without
-- pretending to refresh the underlying certification signal.

create or replace function private.get_effective_vl_cert_health(
  p_max_age interval default interval '30 minutes'
)
returns jsonb
language plpgsql
security definer
stable
set search_path=private,public,pg_temp
as $$
declare
  v_health public.vl_cert_health%rowtype;
  v_age interval;
  v_fresh boolean;
  v_effective_status text;
begin
  if p_max_age < interval '1 minute' then
    raise exception 'health freshness window must be at least one minute' using errcode='22023';
  end if;

  select * into v_health
  from public.vl_cert_health
  order by updated_at desc
  limit 1;

  if not found then
    return jsonb_build_object(
      'status','unknown',
      'source_status',null,
      'fresh',false,
      'updated_at',null,
      'age_seconds',null,
      'reason','no certification health row exists'
    );
  end if;

  v_age := now() - v_health.updated_at;
  v_fresh := v_age <= p_max_age;

  if not v_fresh then
    v_effective_status := 'stale';
  elsif lower(coalesce(v_health.status,''))='ok' then
    v_effective_status := 'ok';
  else
    v_effective_status := coalesce(nullif(v_health.status,''),'unknown');
  end if;

  return jsonb_build_object(
    'status',v_effective_status,
    'source_status',v_health.status,
    'fresh',v_fresh,
    'updated_at',v_health.updated_at,
    'age_seconds',greatest(0,extract(epoch from v_age)::bigint),
    'max_age_seconds',extract(epoch from p_max_age)::bigint,
    'reason',case when v_fresh then 'authoritative health row is within freshness window' else 'authoritative health row is older than freshness window' end
  );
end;
$$;

revoke all on function private.get_effective_vl_cert_health(interval) from public,anon,authenticated;

create or replace function public.get_vl_cert_health_effective(
  p_max_age_seconds integer default 1800
)
returns jsonb
language plpgsql
security definer
stable
set search_path=private,public,pg_temp
as $$
begin
  if p_max_age_seconds < 60 or p_max_age_seconds > 86400 then
    raise exception 'health freshness window must be between 60 and 86400 seconds' using errcode='22023';
  end if;
  return private.get_effective_vl_cert_health(make_interval(secs=>p_max_age_seconds));
end;
$$;

revoke all on function public.get_vl_cert_health_effective(integer) from public,anon,authenticated;
grant execute on function public.get_vl_cert_health_effective(integer) to service_role;


-- VL authoritative certification-health finalizer (candidate contract; NOT auto-deployed)
--
-- Purpose:
--   Replace ad-hoc timestamp refreshes with an evidence-bound finalization step.
--   The function may update public.vl_cert_health only after every ACTIVE builder
--   has a fresh COMPLETE certification run created after p_run_started_at.
--
-- Safety:
--   - no production deployment/promotion/approval mutation;
--   - no builder activation;
--   - no certification evidence/result creation;
--   - failed evidence checks leave public.vl_cert_health untouched;
--   - caller-supplied source/provenance strings are not trusted;
--   - the selected evidence set is SHA-256 bound to a separate human authorization audit record;
--   - authorization must be AAL2, recent, non-replayed and owner/admin scoped across every selected evidence project;
--   - health freshness is anchored to the oldest selected builder evidence timestamp, never clock_timestamp().
--
-- Human authorization record contract:
--   public.audit_logs.action      = 'vl.cert_health_finalization_authorized'
--   public.audit_logs.entity_type = 'vl_cert_health'
--   public.audit_logs.entity_id   = '1'
--   actor_user_id IS NOT NULL
--   metadata contains:
--     run_started_at
--     max_run_age_seconds
--     evidence_digest
--     authenticator_assurance_level = 'aal2'
--
-- Human authorization producer:
--   public.authorize_vl_cert_health_finalization(...)
--   - authenticated human only;
--   - AAL2 required;
--   - records intent only; it cannot update health or lifecycle state;
--   - the finalizer still recomputes evidence, digest, scope and freshness independently.

create or replace view private.vl_cert_health_authorization_request
with (security_barrier = true, security_invoker = true) as
select
  null::timestamptz as run_started_at,
  null::integer as max_run_age_seconds,
  null::text as evidence_digest,
  null::text as reason,
  null::jsonb as result
where false;

revoke all on private.vl_cert_health_authorization_request
  from public,anon,authenticated,service_role;
revoke all (
  run_started_at,max_run_age_seconds,evidence_digest,reason,result
) on private.vl_cert_health_authorization_request
  from public,anon,authenticated,service_role;
grant insert (run_started_at,max_run_age_seconds,evidence_digest,reason),
      select (result)
  on private.vl_cert_health_authorization_request to authenticated;
grant usage on schema private to authenticated;

create or replace function private.authorize_vl_cert_health_finalization_impl()
returns trigger
language plpgsql
security definer
set search_path=''
as $$
declare
  v_now timestamptz := clock_timestamp();
  v_uid uuid := auth.uid();
  v_aal text := coalesce(auth.jwt()->>'aal','aal1');
  v_digest text := lower(btrim(coalesce(new.evidence_digest,'')));
  v_reason text := btrim(coalesce(new.reason,''));
  v_existing_id bigint;
  v_id bigint;
begin
  if tg_op <> 'INSERT'
     or tg_table_schema <> 'private'
     or tg_table_name <> 'vl_cert_health_authorization_request' then
    raise exception 'invalid certification-health authorization entry point' using errcode='42501';
  end if;

  if v_uid is null then
    raise exception 'authenticated human required' using errcode='42501';
  end if;

  if v_aal <> 'aal2' then
    raise exception 'AAL2 MFA required for certification-health authorization' using errcode='42501';
  end if;

  if new.run_started_at is null then
    raise exception 'run_started_at is required' using errcode='22023';
  end if;

  if new.run_started_at > v_now then
    raise exception 'run_started_at cannot be in the future' using errcode='22023';
  end if;

  if new.max_run_age_seconds is null
     or new.max_run_age_seconds < 60
     or new.max_run_age_seconds > 86400 then
    raise exception 'max_run_age_seconds must be between 60 and 86400' using errcode='22023';
  end if;

  if extract(epoch from (v_now-new.run_started_at))::bigint > new.max_run_age_seconds then
    raise exception 'certification run window is already stale' using errcode='22023';
  end if;

  if v_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'evidence_digest must be a lowercase SHA-256 hex digest' using errcode='22023';
  end if;

  if length(v_reason) < 12 then
    raise exception 'authorization reason must be explicit (minimum 12 characters)' using errcode='22023';
  end if;

  if not exists (
    select 1
    from public.project_members pm
    where pm.user_id=v_uid
      and pm.role in ('owner','admin')
  ) then
    raise exception 'owner/admin membership required' using errcode='42501';
  end if;

  select a.id
  into v_existing_id
  from public.audit_logs a
  where a.action='vl.cert_health_finalization_authorized'
    and a.entity_type='vl_cert_health'
    and a.entity_id='1'
    and a.actor_user_id=v_uid
    and a.created_at >= v_now - interval '15 minutes'
    and a.metadata->>'run_started_at'=new.run_started_at::text
    and a.metadata->>'max_run_age_seconds'=new.max_run_age_seconds::text
    and a.metadata->>'evidence_digest'=v_digest
    and not exists (
      select 1
      from public.audit_logs f
      where f.action='vl.cert_health_finalized'
        and f.entity_type='vl_cert_health'
        and f.entity_id='1'
        and f.metadata->>'authorization_audit_id'=a.id::text
    )
  order by a.id desc
  limit 1;

  if v_existing_id is not null then
    new.result := jsonb_build_object(
      'ok',true,
      'decision','already_authorized',
      'authorization_audit_id',v_existing_id,
      'run_started_at',new.run_started_at,
      'max_run_age_seconds',new.max_run_age_seconds,
      'evidence_digest',v_digest
    );
    return new;
  end if;

  insert into public.audit_logs(
    actor_user_id,action,entity_type,entity_id,metadata
  )
  values (
    v_uid,
    'vl.cert_health_finalization_authorized',
    'vl_cert_health',
    '1',
    jsonb_build_object(
      'run_started_at',new.run_started_at,
      'max_run_age_seconds',new.max_run_age_seconds,
      'evidence_digest',v_digest,
      'authenticator_assurance_level',v_aal,
      'reason',v_reason,
      'authorization_scope','FINALIZER_REVALIDATES_ALL_SELECTED_PROJECTS',
      'production_authority_created',false
    )
  )
  returning id into v_id;

  new.result := jsonb_build_object(
    'ok',true,
    'decision','authorized',
    'authorization_audit_id',v_id,
    'run_started_at',new.run_started_at,
    'max_run_age_seconds',new.max_run_age_seconds,
    'evidence_digest',v_digest,
    'production_authority_created',false
  );
  return new;
end;
$$;

revoke all on function private.authorize_vl_cert_health_finalization_impl()
  from public,anon,authenticated,service_role;

drop trigger if exists trg_vl_cert_health_authorization_request
  on private.vl_cert_health_authorization_request;

create trigger trg_vl_cert_health_authorization_request
instead of insert on private.vl_cert_health_authorization_request
for each row execute function private.authorize_vl_cert_health_finalization_impl();

create or replace function public.authorize_vl_cert_health_finalization(
  p_run_started_at timestamptz,
  p_max_run_age_seconds integer,
  p_evidence_digest text,
  p_reason text
)
returns jsonb
language plpgsql
security invoker
set search_path=''
as $$
declare
  v_result jsonb;
begin
  if auth.uid() is null then
    raise exception 'authenticated human required' using errcode='42501';
  end if;

  insert into private.vl_cert_health_authorization_request(
    run_started_at,max_run_age_seconds,evidence_digest,reason
  )
  values (
    p_run_started_at,p_max_run_age_seconds,p_evidence_digest,p_reason
  )
  returning result into v_result;

  if v_result is null then
    raise exception 'certification-health authorization result unavailable' using errcode='42501';
  end if;

  return v_result;
end;
$$;

revoke all on function public.authorize_vl_cert_health_finalization(
  timestamptz,integer,text,text
) from public,anon,service_role;
grant execute on function public.authorize_vl_cert_health_finalization(
  timestamptz,integer,text,text
) to authenticated;

create or replace function private.finalize_vl_cert_health_from_fresh_certification(
  p_run_started_at timestamptz,
  p_max_run_age_seconds integer,
  p_authorization_audit_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path=''
as $$
declare
  v_now timestamptz := clock_timestamp();
  v_age_seconds bigint;
  v_active_registry_count integer;
  v_active_policy_count integer;
  v_failed jsonb := '[]'::jsonb;
  v_passed jsonb := '[]'::jsonb;
  v_evidence_digest text;
  v_health_evidence_at timestamptz;
  v_latest_evidence_at timestamptz;
  v_authorization public.audit_logs%rowtype;
  v_scope_gap_count integer := 0;
  v_effective_health_window_seconds integer := 1800;
  v_updated integer := 0;
begin
  if p_run_started_at is null then
    raise exception 'run_started_at is required' using errcode='22023';
  end if;

  if p_run_started_at > v_now then
    raise exception 'run_started_at cannot be in the future' using errcode='22023';
  end if;

  if p_max_run_age_seconds is null
     or p_max_run_age_seconds < 60
     or p_max_run_age_seconds > 86400 then
    raise exception 'max_run_age_seconds must be between 60 and 86400' using errcode='22023';
  end if;

  if p_authorization_audit_id is null then
    raise exception 'authorization_audit_id is required' using errcode='22023';
  end if;

  v_age_seconds := greatest(0,extract(epoch from (v_now-p_run_started_at))::bigint);

  if v_age_seconds > p_max_run_age_seconds then
    insert into public.audit_logs(action,entity_type,entity_id,metadata)
    values (
      'vl.cert_health_finalization_blocked',
      'vl_cert_health',
      '1',
      jsonb_build_object(
        'reason','RUN_WINDOW_STALE',
        'run_started_at',p_run_started_at,
        'evaluated_at',v_now,
        'run_age_seconds',v_age_seconds,
        'max_run_age_seconds',p_max_run_age_seconds,
        'authorization_audit_id',p_authorization_audit_id
      )
    );

    return jsonb_build_object(
      'ok',false,
      'status','hold',
      'reason','RUN_WINDOW_STALE',
      'run_age_seconds',v_age_seconds,
      'max_run_age_seconds',p_max_run_age_seconds
    );
  end if;

  select count(*)::int
  into v_active_registry_count
  from public.builder_registry
  where status='active';

  select count(*)::int
  into v_active_policy_count
  from public.builder_registry r
  join public.builder_certification_policies p
    on p.builder_key=r.builder_key
   and p.status='active'
  where r.status='active';

  if v_active_registry_count = 0
     or v_active_policy_count <> v_active_registry_count then
    insert into public.audit_logs(action,entity_type,entity_id,metadata)
    values (
      'vl.cert_health_finalization_blocked',
      'vl_cert_health',
      '1',
      jsonb_build_object(
        'reason','ACTIVE_BUILDER_POLICY_MISMATCH',
        'active_registry_count',v_active_registry_count,
        'active_policy_count',v_active_policy_count,
        'run_started_at',p_run_started_at,
        'evaluated_at',v_now,
        'authorization_audit_id',p_authorization_audit_id
      )
    );

    return jsonb_build_object(
      'ok',false,
      'status','hold',
      'reason','ACTIVE_BUILDER_POLICY_MISMATCH',
      'active_registry_count',v_active_registry_count,
      'active_policy_count',v_active_policy_count
    );
  end if;

  with active as (
    select
      r.builder_key,
      p.minimum_score,
      p.minimum_distinct_runs,
      p.required_evidence,
      jsonb_array_length(p.required_evidence) as required_count
    from public.builder_registry r
    join public.builder_certification_policies p
      on p.builder_key=r.builder_key
     and p.status='active'
    where r.status='active'
  ),
  checked as (
    select
      a.*,
      cr.decision,
      cr.score,
      cr.distinct_run_count,
      cr.missing_evidence,
      cr.evaluated_at as result_evaluated_at,
      fr.factory_run_id,
      fr.project_id,
      fr.first_evidence_at,
      fr.last_evidence_at,
      fr.source_uris,
      case
        when cr.decision is null then 'NO_FRESH_CERTIFICATION_RESULT'
        when cr.decision <> 'certified' then 'LATEST_RESULT_NOT_CERTIFIED'
        when cr.score < a.minimum_score then 'CERTIFICATION_SCORE_BELOW_POLICY'
        when cr.distinct_run_count < a.minimum_distinct_runs then 'CERTIFICATION_DEPTH_BELOW_POLICY'
        when coalesce(array_length(cr.missing_evidence,1),0) <> 0 then 'CERTIFICATION_EVIDENCE_MISSING'
        when fr.factory_run_id is null then 'NO_FRESH_COMPLETE_FACTORY_RUN'
        else null
      end as failure_reason
    from active a
    left join lateral (
      select
        r2.decision,
        r2.score,
        r2.distinct_run_count,
        r2.missing_evidence,
        r2.evaluated_at
      from public.builder_certification_results r2
      where r2.builder_key=a.builder_key
        and r2.evaluated_at >= p_run_started_at
      order by r2.evaluated_at desc,r2.id desc
      limit 1
    ) cr on true
    left join lateral (
      select
        e.factory_run_id,
        f.project_id,
        min(e.created_at) as first_evidence_at,
        max(e.created_at) as last_evidence_at,
        array_agg(distinct e.source_uri order by e.source_uri) as source_uris
      from public.builder_certification_evidence e
      join public.factory_runs f on f.id=e.factory_run_id
      where e.builder_key=a.builder_key
        and e.evidence_status='pass'
        and e.created_at >= p_run_started_at
        and e.source_uri is not null
        and btrim(e.source_uri) <> ''
        and f.target_environment='staging'
        and f.production_locked is true
        and f.state='awaiting_approval'
        and e.evidence_type = any (
          array(select jsonb_array_elements_text(a.required_evidence))
        )
      group by e.factory_run_id,f.project_id
      having count(distinct e.evidence_type)=a.required_count
      order by max(e.created_at) desc,e.factory_run_id
      limit 1
    ) fr on true
  )
  select
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'builder_key',builder_key,
          'reason',failure_reason,
          'result_evaluated_at',result_evaluated_at,
          'factory_run_id',factory_run_id,
          'project_id',project_id
        )
        order by builder_key
      ) filter (where failure_reason is not null),
      '[]'::jsonb
    ),
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'builder_key',builder_key,
          'factory_run_id',factory_run_id,
          'project_id',project_id,
          'result_evaluated_at',result_evaluated_at,
          'first_evidence_at',first_evidence_at,
          'last_evidence_at',last_evidence_at,
          'source_uris',to_jsonb(source_uris),
          'score',score,
          'distinct_run_count',distinct_run_count
        )
        order by builder_key
      ) filter (where failure_reason is null),
      '[]'::jsonb
    )
  into v_failed,v_passed
  from checked;

  if jsonb_array_length(v_failed) > 0 then
    insert into public.audit_logs(action,entity_type,entity_id,metadata)
    values (
      'vl.cert_health_finalization_blocked',
      'vl_cert_health',
      '1',
      jsonb_build_object(
        'reason','FRESH_CERTIFICATION_INCOMPLETE',
        'run_started_at',p_run_started_at,
        'evaluated_at',v_now,
        'run_age_seconds',v_age_seconds,
        'max_run_age_seconds',p_max_run_age_seconds,
        'authorization_audit_id',p_authorization_audit_id,
        'failed_builders',v_failed,
        'passed_builders',v_passed
      )
    );

    return jsonb_build_object(
      'ok',false,
      'status','hold',
      'reason','FRESH_CERTIFICATION_INCOMPLETE',
      'failed_builders',v_failed,
      'passed_builders',v_passed
    );
  end if;

  if jsonb_array_length(v_passed) <> v_active_registry_count then
    raise exception 'candidate builder count mismatch' using errcode='P0001';
  end if;

  if exists (
    select 1
    from jsonb_array_elements(v_passed) b
    join public.deployments d
      on d.factory_run_id=(b->>'factory_run_id')::uuid
    join public.environments e
      on e.id=d.environment_id
    where e.kind='production'
      and (
        d.status in ('approved','deploying','deployed')
        or d.approved_by is not null
        or d.deployed_at is not null
      )
  ) then
    insert into public.audit_logs(action,entity_type,entity_id,metadata)
    values (
      'vl.cert_health_finalization_blocked',
      'vl_cert_health',
      '1',
      jsonb_build_object(
        'reason','SELECTED_EVIDENCE_RUN_HAS_PRODUCTION_AUTHORITY',
        'run_started_at',p_run_started_at,
        'evaluated_at',v_now,
        'authorization_audit_id',p_authorization_audit_id,
        'passed_builders',v_passed
      )
    );

    return jsonb_build_object(
      'ok',false,
      'status','hold',
      'reason','SELECTED_EVIDENCE_RUN_HAS_PRODUCTION_AUTHORITY'
    );
  end if;

  v_evidence_digest := encode(
    extensions.digest(convert_to(v_passed::text,'UTF8'),'sha256'),
    'hex'
  );

  select
    min((b->>'last_evidence_at')::timestamptz),
    max((b->>'last_evidence_at')::timestamptz)
  into v_health_evidence_at,v_latest_evidence_at
  from jsonb_array_elements(v_passed) b;

  if v_health_evidence_at is null or v_latest_evidence_at is null then
    raise exception 'selected certification evidence timestamp missing' using errcode='P0001';
  end if;

  if v_health_evidence_at < v_now - make_interval(secs=>v_effective_health_window_seconds) then
    insert into public.audit_logs(action,entity_type,entity_id,metadata)
    values (
      'vl.cert_health_finalization_blocked',
      'vl_cert_health',
      '1',
      jsonb_build_object(
        'reason','EVIDENCE_TOO_OLD_FOR_EFFECTIVE_HEALTH',
        'run_started_at',p_run_started_at,
        'evaluated_at',v_now,
        'health_evidence_at',v_health_evidence_at,
        'latest_evidence_at',v_latest_evidence_at,
        'effective_health_window_seconds',v_effective_health_window_seconds,
        'authorization_audit_id',p_authorization_audit_id
      )
    );

    return jsonb_build_object(
      'ok',false,
      'status','hold',
      'reason','EVIDENCE_TOO_OLD_FOR_EFFECTIVE_HEALTH',
      'health_evidence_at',v_health_evidence_at,
      'effective_health_window_seconds',v_effective_health_window_seconds
    );
  end if;

  select *
  into v_authorization
  from public.audit_logs
  where id=p_authorization_audit_id
  for update;

  if not found then
    insert into public.audit_logs(action,entity_type,entity_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',
      jsonb_build_object(
        'reason','AUTHORIZATION_NOT_FOUND',
        'authorization_audit_id',p_authorization_audit_id,
        'evidence_digest',v_evidence_digest,
        'run_started_at',p_run_started_at
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_NOT_FOUND');
  end if;

  if v_authorization.action <> 'vl.cert_health_finalization_authorized'
     or v_authorization.entity_type is distinct from 'vl_cert_health'
     or v_authorization.entity_id is distinct from '1'
     or v_authorization.actor_user_id is null then
    insert into public.audit_logs(action,entity_type,entity_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',
      jsonb_build_object(
        'reason','AUTHORIZATION_RECORD_INVALID',
        'authorization_audit_id',p_authorization_audit_id,
        'evidence_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_RECORD_INVALID');
  end if;

  if coalesce(v_authorization.metadata->>'authenticator_assurance_level','') <> 'aal2' then
    insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
      jsonb_build_object(
        'reason','AUTHORIZATION_AAL2_REQUIRED',
        'authorization_audit_id',p_authorization_audit_id,
        'evidence_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_AAL2_REQUIRED');
  end if;

  if coalesce(v_authorization.metadata->>'evidence_digest','') <> v_evidence_digest then
    insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
      jsonb_build_object(
        'reason','AUTHORIZATION_EVIDENCE_DIGEST_MISMATCH',
        'authorization_audit_id',p_authorization_audit_id,
        'authorized_digest',v_authorization.metadata->>'evidence_digest',
        'current_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_EVIDENCE_DIGEST_MISMATCH');
  end if;

  begin
    if (v_authorization.metadata->>'run_started_at')::timestamptz is distinct from p_run_started_at
       or (v_authorization.metadata->>'max_run_age_seconds')::integer is distinct from p_max_run_age_seconds then
      insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
      values (
        'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
        jsonb_build_object(
          'reason','AUTHORIZATION_RUN_BINDING_MISMATCH',
          'authorization_audit_id',p_authorization_audit_id,
          'evidence_digest',v_evidence_digest
        )
      );
      return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_RUN_BINDING_MISMATCH');
    end if;
  exception when others then
    insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
      jsonb_build_object(
        'reason','AUTHORIZATION_RUN_BINDING_INVALID',
        'authorization_audit_id',p_authorization_audit_id,
        'evidence_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_RUN_BINDING_INVALID');
  end;

  if v_authorization.created_at < v_latest_evidence_at then
    insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
      jsonb_build_object(
        'reason','AUTHORIZATION_PREDATES_EVIDENCE',
        'authorization_audit_id',p_authorization_audit_id,
        'authorization_created_at',v_authorization.created_at,
        'latest_evidence_at',v_latest_evidence_at,
        'evidence_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_PREDATES_EVIDENCE');
  end if;

  if v_authorization.created_at < v_now - interval '15 minutes' then
    insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
      jsonb_build_object(
        'reason','AUTHORIZATION_STALE',
        'authorization_audit_id',p_authorization_audit_id,
        'authorization_created_at',v_authorization.created_at,
        'evaluated_at',v_now,
        'evidence_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_STALE');
  end if;

  select count(*)::int
  into v_scope_gap_count
  from (
    select distinct (b->>'project_id')::uuid as project_id
    from jsonb_array_elements(v_passed) b
  ) selected_projects
  where not exists (
    select 1
    from public.project_members pm
    where pm.project_id=selected_projects.project_id
      and pm.user_id=v_authorization.actor_user_id
      and pm.role in ('owner','admin')
  );

  if v_scope_gap_count <> 0 then
    insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
      jsonb_build_object(
        'reason','AUTHORIZATION_SCOPE_MISMATCH',
        'authorization_audit_id',p_authorization_audit_id,
        'scope_gap_count',v_scope_gap_count,
        'evidence_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_SCOPE_MISMATCH');
  end if;

  if exists (
    select 1
    from public.audit_logs a
    where a.action='vl.cert_health_finalized'
      and a.entity_type='vl_cert_health'
      and a.entity_id='1'
      and a.metadata->>'authorization_audit_id'=p_authorization_audit_id::text
  ) then
    insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
    values (
      'vl.cert_health_finalization_blocked','vl_cert_health','1',v_authorization.actor_user_id,
      jsonb_build_object(
        'reason','AUTHORIZATION_REPLAYED',
        'authorization_audit_id',p_authorization_audit_id,
        'evidence_digest',v_evidence_digest
      )
    );
    return jsonb_build_object('ok',false,'status','hold','reason','AUTHORIZATION_REPLAYED');
  end if;

  update public.vl_cert_health
  set status='ok',
      updated_at=v_health_evidence_at
  where id=1;

  get diagnostics v_updated = row_count;

  if v_updated <> 1 then
    raise exception 'expected exactly one vl_cert_health row, updated %',v_updated;
  end if;

  insert into public.audit_logs(action,entity_type,entity_id,actor_user_id,metadata)
  values (
    'vl.cert_health_finalized',
    'vl_cert_health',
    '1',
    v_authorization.actor_user_id,
    jsonb_build_object(
      'status','ok',
      'run_started_at',p_run_started_at,
      'evaluated_at',v_now,
      'health_evidence_at',v_health_evidence_at,
      'latest_evidence_at',v_latest_evidence_at,
      'run_age_seconds',v_age_seconds,
      'max_run_age_seconds',p_max_run_age_seconds,
      'authorization_audit_id',p_authorization_audit_id,
      'evidence_digest',v_evidence_digest,
      'active_builder_count',v_active_registry_count,
      'builders',v_passed
    )
  );

  return jsonb_build_object(
    'ok',true,
    'status','ok',
    'updated_at',v_health_evidence_at,
    'authorization_audit_id',p_authorization_audit_id,
    'evidence_digest',v_evidence_digest,
    'active_builder_count',v_active_registry_count,
    'builders',v_passed
  );
end;
$$;

revoke all on function private.finalize_vl_cert_health_from_fresh_certification(
  timestamptz,integer,bigint
) from public,anon,authenticated;

grant execute on function private.finalize_vl_cert_health_from_fresh_certification(
  timestamptz,integer,bigint
) to service_role;

