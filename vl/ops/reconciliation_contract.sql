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

  -- Hard exclusion: if any deployment row points at a logical production environment,
  -- this automatic historical reconciliation path must not touch the run.
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

  -- Idempotent terminal pairs.
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

  -- A known failed factory run may only align the still-running workflow to failed.
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

  -- An incomplete historical validating run is cancelled, never promoted to certified.
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

  -- Never bulk-dispose anything with any production-environment deployment row.
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
