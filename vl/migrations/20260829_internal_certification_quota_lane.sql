-- Separate controlled internal certification runs from customer/public factory quotas.
-- The exemption is transaction-local and can only be activated inside the service-role-only
-- golden certification RPC. It remains staging-only and production-locked.

begin;

create or replace function private.enforce_public_factory_quota()
returns trigger
language plpgsql
security definer
set search_path = public, private, auth, pg_temp
as $$
declare
  v_account public.customer_accounts%rowtype;
  v_daily_limit int;
  v_concurrent_limit int;
  v_daily_used int;
  v_active int;
begin
  if coalesce(current_setting('vrs.certification_depth_authorized', true),'')='true'
     and coalesce((new.input->>'certification_depth_run')::boolean,false)=true
     and new.target_environment='staging'
     and new.production_locked is true then
    return new;
  end if;

  select * into v_account from public.customer_accounts where owner_user_id=new.requested_by;
  if not found then return new; end if;

  if v_account.status<>'active' or v_account.onboarding_state<>'ready' or v_account.terms_accepted_at is null then
    raise exception 'customer account is not launch-ready' using errcode='42501';
  end if;

  select coalesce((limits->>'factory_runs_per_day')::int,0), coalesce((limits->>'concurrent_runs')::int,0)
    into v_daily_limit,v_concurrent_limit from public.plan_catalog where plan_key=v_account.plan_key and is_public=true;
  if v_daily_limit<=0 or v_concurrent_limit<=0 then raise exception 'plan quota is not configured' using errcode='42501'; end if;

  select count(*) into v_daily_used from public.factory_runs
   where requested_by=new.requested_by and created_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'
     and coalesce((input->>'certification_depth_run')::boolean,false)=false;
  if v_daily_used>=v_daily_limit then raise exception 'daily factory run quota exceeded' using errcode='P0001'; end if;

  -- Concurrency means actual build execution capacity, not records waiting for human approval.
  select count(*) into v_active
  from private.runner_jobs rj
  join public.factory_runs fr on fr.id=rj.factory_run_id
  where fr.requested_by=new.requested_by
    and rj.state in ('queued','leased','running')
    and coalesce((fr.input->>'certification_depth_run')::boolean,false)=false;
  if v_active>=v_concurrent_limit then raise exception 'concurrent factory run quota exceeded' using errcode='P0001'; end if;

  insert into private.usage_counters(customer_account_id,metric_key,window_start,window_end,used_count,limit_count)
  values(v_account.id,'factory_runs',date_trunc('day',now() at time zone 'UTC') at time zone 'UTC',(date_trunc('day',now() at time zone 'UTC')+interval '1 day') at time zone 'UTC',v_daily_used+1,v_daily_limit)
  on conflict(customer_account_id,metric_key,window_start,window_end) do update set used_count=excluded.used_count,limit_count=excluded.limit_count,updated_at=now();

  return new;
end
$$;

create or replace function public.enqueue_vrs_golden_certification_runs(
  p_builder_key text,
  p_run_count integer default 1
)
returns jsonb
language plpgsql
security definer
set search_path = private, public, pg_temp
as $$
declare
  v_profile private.builder_certification_golden_profiles%rowtype;
  v_spec public.app_specs%rowtype;
  v_project public.projects%rowtype;
  v_builder public.builder_registry%rowtype;
  v_workflow_id uuid;
  v_run_id uuid;
  v_ids jsonb := '[]'::jsonb;
  v_actor uuid;
  i integer;
begin
  if current_user not in ('service_role','postgres') then
    raise exception 'service-role certification authority required';
  end if;

  select * into v_profile
  from private.builder_certification_golden_profiles
  where builder_key=p_builder_key and enabled=true;
  if not found then raise exception 'builder is not whitelisted for golden certification'; end if;

  if p_run_count is null or p_run_count < 1 or p_run_count > v_profile.max_batch_runs then
    raise exception 'run_count outside locked certification batch limit';
  end if;

  select * into v_builder from public.builder_registry
  where builder_key=p_builder_key and status='active';
  if not found then raise exception 'only active builders may use golden certification rerun authority'; end if;

  select p.* into v_project
  from public.projects p
  where p.name=v_profile.project_name
  order by p.created_at desc
  limit 1;
  if not found then raise exception 'whitelisted golden project not found'; end if;

  select a.* into v_spec
  from public.app_specs a
  where a.project_id=v_project.id
    and a.status='approved'
    and (v_profile.app_spec_title is null or a.title=v_profile.app_spec_title)
    and (
      p_builder_key='mobile-flutter-v1'
      or coalesce(a.spec #>> '{selected_builder,builder_key}',a.spec #>> '{routing,selected_builder,builder_key}')=p_builder_key
    )
  order by a.approved_at desc nulls last,a.created_at desc
  limit 1;
  if not found then raise exception 'approved whitelisted golden app spec not found'; end if;

  v_actor:=coalesce(v_spec.approved_by,v_spec.created_by);
  if v_actor is null then raise exception 'golden spec has no accountable actor'; end if;
  if not exists (
    select 1 from public.project_members pm
    where pm.project_id=v_project.id and pm.user_id=v_actor and pm.role in ('owner','admin','builder')
  ) then raise exception 'golden spec actor is not an authorized project member'; end if;

  if not exists (
    select 1 from public.environments e
    where e.project_id=v_project.id and e.kind='production' and e.status='ready'
  ) then raise exception 'ready production environment metadata required for release-candidate verification'; end if;

  -- Transaction-local authority. The public quota trigger only honors this when the row is
  -- explicitly an internal certification-depth staging run and remains production-locked.
  perform set_config('vrs.certification_depth_authorized','true',true);

  for i in 1..p_run_count loop
    insert into public.workflows(project_id,app_spec_id,workflow_type,state,input,created_by)
    values(
      v_project.id,v_spec.id,'factory_build_v2','queued',
      jsonb_build_object(
        'builder_key',p_builder_key,
        'target_environment','staging',
        'target_platforms',to_jsonb(v_profile.target_platforms),
        'certification_depth_run',true,
        'certification_batch_index',i,
        'production_locked',true
      ),v_actor
    ) returning id into v_workflow_id;

    insert into public.factory_runs(
      project_id,app_spec_id,workflow_id,requested_by,run_type,state,
      target_environment,production_locked,input,plan,target_platforms
    ) values (
      v_project.id,v_spec.id,v_workflow_id,v_actor,'build','planning',
      'staging',true,
      jsonb_build_object(
        'builder_key',p_builder_key,
        'generator_version','certification-depth-v1',
        'certification_depth_run',true,
        'certification_batch_index',i
      ),
      jsonb_build_object(
        'purpose','current-policy-certification-depth',
        'builder_key',p_builder_key,
        'builders',jsonb_build_array(jsonb_build_object('key',p_builder_key))
      ),
      v_profile.target_platforms
    ) returning id into v_run_id;

    v_ids:=v_ids || jsonb_build_array(jsonb_build_object(
      'factory_run_id',v_run_id,
      'workflow_id',v_workflow_id,
      'builder_key',p_builder_key,
      'target_environment','staging',
      'production_locked',true
    ));
  end loop;

  return jsonb_build_object(
    'ok',true,
    'builder_key',p_builder_key,
    'run_count',p_run_count,
    'runs',v_ids,
    'production_locked',true,
    'production_approval_performed',false,
    'production_promotion_performed',false,
    'public_customer_quota_consumed',false
  );
end;
$$;

revoke all on function public.enqueue_vrs_golden_certification_runs(text,integer) from public,anon,authenticated;
grant execute on function public.enqueue_vrs_golden_certification_runs(text,integer) to service_role;

commit;
