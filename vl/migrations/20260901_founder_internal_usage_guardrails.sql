-- Founder/internal build mode: bypass customer pay-first only, never cost accounting or release governance.
-- Staging-only, production-locked, owner/admin-only. Over-limit use requires explicit time-bounded override.

begin;

create table if not exists private.internal_usage_policy (
  singleton boolean primary key default true check (singleton),
  enabled boolean not null default true,
  daily_run_limit integer not null check (daily_run_limit > 0),
  concurrent_run_limit integer not null check (concurrent_run_limit > 0),
  daily_estimated_cost_unit_limit bigint not null check (daily_estimated_cost_unit_limit > 0),
  updated_at timestamptz not null default now()
);

insert into private.internal_usage_policy(singleton,enabled,daily_run_limit,concurrent_run_limit,daily_estimated_cost_unit_limit)
values(true,true,20,3,100000)
on conflict(singleton) do nothing;

create table if not exists private.internal_usage_overrides (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  requested_by uuid not null,
  reason text not null check (length(btrim(reason)) >= 12),
  valid_from timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (expires_at > valid_from),
  check (expires_at <= valid_from + interval '4 hours')
);
create index if not exists internal_usage_overrides_active_idx
  on private.internal_usage_overrides(project_id,requested_by,expires_at)
  where revoked_at is null;

create table if not exists private.internal_usage_ledger (
  id uuid primary key default gen_random_uuid(),
  factory_run_id uuid not null unique,
  project_id uuid not null references public.projects(id) on delete cascade,
  requested_by uuid not null,
  classification text not null check (classification in ('r_and_d','vl_maintenance','demo','customer_poc','internal_commercial_project')),
  estimated_cost_units bigint not null check (estimated_cost_units >= 0),
  actual_cost_units bigint,
  override_id uuid references private.internal_usage_overrides(id),
  recorded_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (actual_cost_units is null or actual_cost_units >= 0)
);
create index if not exists internal_usage_ledger_actor_day_idx
  on private.internal_usage_ledger(requested_by,recorded_at);

create table if not exists private.internal_usage_audit (
  id uuid primary key default gen_random_uuid(),
  factory_run_id uuid,
  project_id uuid not null,
  actor_user_id uuid not null,
  event_type text not null,
  reason text,
  evidence jsonb not null default '{}'::jsonb,
  recorded_at timestamptz not null default now()
);

alter table private.internal_usage_policy enable row level security;
alter table private.internal_usage_overrides enable row level security;
alter table private.internal_usage_ledger enable row level security;
alter table private.internal_usage_audit enable row level security;
revoke all on private.internal_usage_policy,private.internal_usage_overrides,private.internal_usage_ledger,private.internal_usage_audit from public,anon,authenticated;

create or replace function public.request_vrs_internal_usage_override(
  p_project_id uuid,
  p_reason text,
  p_duration_minutes integer default 60
)
returns jsonb
language plpgsql
security definer
set search_path = private, public, auth, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_aal text := coalesce(auth.jwt()->>'aal','aal1');
  v_id uuid;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for internal usage override'; end if;
  if p_duration_minutes < 1 or p_duration_minutes > 240 then raise exception 'override duration outside 1..240 minutes'; end if;
  if length(btrim(coalesce(p_reason,''))) < 12 then raise exception 'override reason must be explicit'; end if;
  if not exists (
    select 1 from public.project_members pm
    where pm.project_id=p_project_id and pm.user_id=v_uid and pm.role in ('owner','admin')
  ) then raise exception 'owner/admin internal override authority required'; end if;

  insert into private.internal_usage_overrides(project_id,requested_by,reason,expires_at)
  values(p_project_id,v_uid,btrim(p_reason),now()+make_interval(mins=>p_duration_minutes))
  returning id into v_id;

  insert into private.internal_usage_audit(project_id,actor_user_id,event_type,reason,evidence)
  values(p_project_id,v_uid,'override_created',btrim(p_reason),jsonb_build_object(
    'override_id',v_id,'duration_minutes',p_duration_minutes,'aal',v_aal,
    'production_approval_changed',false,'production_promotion_changed',false
  ));

  return jsonb_build_object('ok',true,'override_id',v_id,'expires_in_minutes',p_duration_minutes,
    'production_approval_bypassed',false,'production_promotion_bypassed',false);
end;
$$;
revoke all on function public.request_vrs_internal_usage_override(uuid,text,integer) from public,anon;
grant execute on function public.request_vrs_internal_usage_override(uuid,text,integer) to authenticated;

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
  v_policy private.internal_usage_policy%rowtype;
  v_internal_daily int;
  v_internal_active int;
  v_internal_cost bigint;
  v_estimated_cost bigint;
  v_classification text;
  v_override private.internal_usage_overrides%rowtype;
begin
  if coalesce(current_setting('vrs.certification_depth_authorized', true),'')='true'
     and coalesce((new.input->>'certification_depth_run')::boolean,false)=true
     and new.target_environment='staging'
     and new.production_locked is true then
    return new;
  end if;

  if coalesce(new.input->>'build_mode','')='founder_internal' then
    if new.target_environment <> 'staging' or new.production_locked is distinct from true then
      raise exception 'founder/internal entry must be staging-only and production-locked' using errcode='42501';
    end if;
    if not exists (
      select 1 from public.project_members pm
      where pm.project_id=new.project_id and pm.user_id=new.requested_by and pm.role in ('owner','admin')
    ) then raise exception 'owner/admin founder/internal authority required' using errcode='42501'; end if;

    v_classification := nullif(new.input->>'internal_usage_classification','');
    if v_classification not in ('r_and_d','vl_maintenance','demo','customer_poc','internal_commercial_project') then
      raise exception 'valid internal usage classification required' using errcode='P0001';
    end if;
    begin v_estimated_cost := (new.input->>'estimated_cost_units')::bigint;
    exception when others then raise exception 'estimated_cost_units integer required' using errcode='P0001'; end;
    if v_estimated_cost < 0 then raise exception 'estimated_cost_units must be non-negative' using errcode='P0001'; end if;

    select * into v_policy from private.internal_usage_policy where singleton=true and enabled=true;
    if not found then raise exception 'founder/internal usage policy unavailable' using errcode='42501'; end if;

    select count(*) into v_internal_daily from private.internal_usage_ledger
      where requested_by=new.requested_by and recorded_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC';
    select coalesce(sum(estimated_cost_units),0) into v_internal_cost from private.internal_usage_ledger
      where requested_by=new.requested_by and recorded_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC';
    select count(*) into v_internal_active
      from private.runner_jobs rj join public.factory_runs fr on fr.id=rj.factory_run_id
      where fr.requested_by=new.requested_by and coalesce(fr.input->>'build_mode','')='founder_internal'
        and rj.state in ('queued','leased','running');

    if v_internal_daily >= v_policy.daily_run_limit
       or v_internal_active >= v_policy.concurrent_run_limit
       or v_internal_cost + v_estimated_cost > v_policy.daily_estimated_cost_unit_limit then
      select * into v_override from private.internal_usage_overrides o
      where o.project_id=new.project_id and o.requested_by=new.requested_by
        and o.revoked_at is null and o.valid_from<=now() and o.expires_at>now()
      order by o.created_at desc limit 1;
      if not found then raise exception 'founder/internal usage limit exceeded; explicit active override required' using errcode='P0001'; end if;
    end if;

    insert into private.internal_usage_ledger(factory_run_id,project_id,requested_by,classification,estimated_cost_units,override_id)
    values(new.id,new.project_id,new.requested_by,v_classification,v_estimated_cost,v_override.id);
    insert into private.internal_usage_audit(factory_run_id,project_id,actor_user_id,event_type,reason,evidence)
    values(new.id,new.project_id,new.requested_by,'internal_run_admitted',v_override.reason,jsonb_build_object(
      'classification',v_classification,'estimated_cost_units',v_estimated_cost,
      'daily_used_before',v_internal_daily,'concurrent_used_before',v_internal_active,
      'daily_estimated_cost_before',v_internal_cost,'override_id',v_override.id,
      'target_environment',new.target_environment,'production_locked',new.production_locked,
      'production_approval_bypassed',false,'production_promotion_bypassed',false
    ));
    return new;
  end if;

  select * into v_account from public.customer_accounts where owner_user_id=new.requested_by;
  if not found then return new; end if;
  if v_account.status<>'active' or v_account.onboarding_state<>'ready' or v_account.terms_accepted_at is null then
    raise exception 'customer account is not launch-ready' using errcode='42501';
  end if;
  select coalesce((limits->>'factory_runs_per_day')::int,0),coalesce((limits->>'concurrent_runs')::int,0)
    into v_daily_limit,v_concurrent_limit from public.plan_catalog where plan_key=v_account.plan_key and is_public=true;
  if v_daily_limit<=0 or v_concurrent_limit<=0 then raise exception 'plan quota is not configured' using errcode='42501'; end if;
  select count(*) into v_daily_used from public.factory_runs where requested_by=new.requested_by
    and created_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'
    and coalesce((input->>'certification_depth_run')::boolean,false)=false
    and coalesce(input->>'build_mode','')<>'founder_internal';
  if v_daily_used>=v_daily_limit then raise exception 'daily factory run quota exceeded' using errcode='P0001'; end if;
  select count(*) into v_active from private.runner_jobs rj join public.factory_runs fr on fr.id=rj.factory_run_id
    where fr.requested_by=new.requested_by and rj.state in ('queued','leased','running')
      and coalesce((fr.input->>'certification_depth_run')::boolean,false)=false
      and coalesce(fr.input->>'build_mode','')<>'founder_internal';
  if v_active>=v_concurrent_limit then raise exception 'concurrent factory run quota exceeded' using errcode='P0001'; end if;
  insert into private.usage_counters(customer_account_id,metric_key,window_start,window_end,used_count,limit_count)
  values(v_account.id,'factory_runs',date_trunc('day',now() at time zone 'UTC') at time zone 'UTC',
    (date_trunc('day',now() at time zone 'UTC')+interval '1 day') at time zone 'UTC',v_daily_used+1,v_daily_limit)
  on conflict(customer_account_id,metric_key,window_start,window_end) do update
    set used_count=excluded.used_count,limit_count=excluded.limit_count,updated_at=now();
  return new;
end;
$$;

commit;
