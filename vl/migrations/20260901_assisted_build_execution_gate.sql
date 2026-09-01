-- VL Assisted Build execution gate
-- Policy/config driven Factory Credit estimate and launch-pilot entitlement.
-- No production payment, production approval, or production promotion authority is introduced.

create table if not exists private.assisted_build_cost_policy (
  complexity_class text primary key check (complexity_class in ('low','medium','high')),
  factory_credit_estimate integer not null check (factory_credit_estimate > 0 and factory_credit_estimate <= 100),
  service_tier text not null,
  enabled boolean not null default true,
  updated_at timestamptz not null default now()
);

alter table private.assisted_build_cost_policy enable row level security;
revoke all on table private.assisted_build_cost_policy from public, anon, authenticated;

insert into private.assisted_build_cost_policy(complexity_class,factory_credit_estimate,service_tier,enabled)
values
  ('low',1,'Assisted Build',true),
  ('medium',2,'Assisted Build',true),
  ('high',3,'Custom / Enterprise',true)
on conflict (complexity_class) do update
set factory_credit_estimate=excluded.factory_credit_estimate,
    service_tier=excluded.service_tier,
    enabled=excluded.enabled,
    updated_at=now();

-- Pilot entitlement is explicitly policy/config driven and is not a paid-credit substitute.
-- Paid commercial execution remains fail-closed until verified payment/credit evidence exists.
update public.plan_catalog
set limits = coalesce(limits,'{}'::jsonb) || jsonb_build_object(
  'assisted_build_execution_mode','pilot_entitlement',
  'assisted_build_factory_credits_per_day',6
)
where plan_key='launch_pilot' and is_public=true;

create or replace function public.vl_get_assisted_build_quote(p_complexity text)
returns jsonb
language plpgsql
security definer
set search_path=private,public,auth,pg_temp
as $$
declare
  v_policy private.assisted_build_cost_policy%rowtype;
begin
  if auth.uid() is null then
    raise exception 'authenticated user required' using errcode='42501';
  end if;

  select * into v_policy
  from private.assisted_build_cost_policy
  where complexity_class=p_complexity and enabled=true;

  if not found then
    raise exception 'assisted build cost policy unavailable' using errcode='P0001';
  end if;

  return jsonb_build_object(
    'complexity_class',v_policy.complexity_class,
    'factory_credit_estimate',v_policy.factory_credit_estimate,
    'service_tier_recommendation',v_policy.service_tier,
    'pricing_source','private.assisted_build_cost_policy',
    'commercial_amount',null,
    'production_payment_performed',false
  );
end;
$$;

revoke all on function public.vl_get_assisted_build_quote(text) from public, anon;
grant execute on function public.vl_get_assisted_build_quote(text) to authenticated;

create or replace function private.enforce_assisted_build_execution_gate()
returns trigger
language plpgsql
security definer
set search_path=public,private,auth,pg_temp
as $$
declare
  v_spec public.app_specs%rowtype;
  v_policy private.assisted_build_cost_policy%rowtype;
  v_account public.customer_accounts%rowtype;
  v_limits jsonb;
  v_mode text;
  v_allowance integer;
  v_estimate integer;
  v_used integer;
  v_complexity text;
  v_builder_key text;
  v_confirmed_at text;
begin
  select * into v_spec from public.app_specs where id=new.app_spec_id;
  if not found or coalesce(v_spec.spec->>'source','') <> 'assisted_build' then
    return new;
  end if;

  if new.target_environment <> 'staging' or new.production_locked is distinct from true then
    raise exception 'assisted build execution must be staging-only and production-locked' using errcode='42501';
  end if;

  if coalesce((v_spec.spec #>> '{provenance,user_confirmed}')::boolean,false) is distinct from true then
    raise exception 'assisted build customer confirmation required' using errcode='P0001';
  end if;
  v_confirmed_at := nullif(v_spec.spec #>> '{provenance,confirmed_at}','');
  if v_confirmed_at is null then
    raise exception 'assisted build confirmation timestamp required' using errcode='P0001';
  end if;

  v_builder_key := nullif(v_spec.spec #>> '{selected_builder,builder_key}','');
  if v_builder_key is null then
    raise exception 'assisted build selected builder contract required' using errcode='P0001';
  end if;

  v_complexity := nullif(v_spec.spec #>> '{complexity,classification}','');
  select * into v_policy
  from private.assisted_build_cost_policy
  where complexity_class=v_complexity and enabled=true;
  if not found then
    raise exception 'assisted build authoritative cost policy unavailable' using errcode='P0001';
  end if;

  begin
    v_estimate := (v_spec.spec #>> '{commercial,factory_credit_estimate}')::integer;
  exception when others then
    raise exception 'assisted build Factory Credit estimate required' using errcode='P0001';
  end;
  if v_estimate is distinct from v_policy.factory_credit_estimate then
    raise exception 'assisted build Factory Credit estimate does not match authoritative policy' using errcode='P0001';
  end if;

  -- Serialize customer Assisted Build admissions so daily credit accounting cannot race.
  select * into v_account
  from public.customer_accounts
  where owner_user_id=new.requested_by
  for update;
  if not found or v_account.status <> 'active' or v_account.onboarding_state <> 'ready' or v_account.terms_accepted_at is null then
    raise exception 'launch-ready customer account required for assisted build execution' using errcode='42501';
  end if;

  select limits into v_limits
  from public.plan_catalog
  where plan_key=v_account.plan_key and is_public=true;
  if v_limits is null then
    raise exception 'assisted build plan policy unavailable' using errcode='42501';
  end if;

  v_mode := coalesce(v_limits->>'assisted_build_execution_mode','');
  begin
    v_allowance := coalesce((v_limits->>'assisted_build_factory_credits_per_day')::integer,0);
  exception when others then
    v_allowance := 0;
  end;

  -- V1 permits only an explicit launch-pilot entitlement. Paid mode is intentionally fail-closed
  -- until verified payment/credit evidence is implemented and separately governed.
  if v_mode <> 'pilot_entitlement' or v_allowance <= 0 then
    raise exception 'assisted build execution authorization unavailable; verified credit/payment required' using errcode='42501';
  end if;

  select coalesce(sum((fr.input #>> '{assisted_build_execution_authorization,factory_credit_estimate}')::integer),0)
  into v_used
  from public.factory_runs fr
  where fr.requested_by=new.requested_by
    and fr.created_at >= (date_trunc('day',now() at time zone 'UTC') at time zone 'UTC')
    and fr.input ? 'assisted_build_execution_authorization';

  if v_used + v_estimate > v_allowance then
    raise exception 'assisted build daily Factory Credit allowance exceeded' using errcode='P0001';
  end if;

  new.input := coalesce(new.input,'{}'::jsonb) || jsonb_build_object(
    'assisted_build_execution_authorization',jsonb_build_object(
      'source','pilot_entitlement',
      'plan_key',v_account.plan_key,
      'factory_credit_estimate',v_estimate,
      'daily_factory_credit_allowance',v_allowance,
      'daily_factory_credit_used_before',v_used,
      'pricing_source','private.assisted_build_cost_policy',
      'commercial_payment_bypassed',false,
      'production_approval_bypassed',false,
      'production_promotion_bypassed',false
    )
  );

  insert into private.usage_counters(customer_account_id,metric_key,window_start,window_end,used_count,limit_count)
  values(
    v_account.id,
    'assisted_build_factory_credits',
    date_trunc('day',now() at time zone 'UTC') at time zone 'UTC',
    (date_trunc('day',now() at time zone 'UTC')+interval '1 day') at time zone 'UTC',
    v_used+v_estimate,
    v_allowance
  )
  on conflict(customer_account_id,metric_key,window_start,window_end) do update
  set used_count=excluded.used_count,limit_count=excluded.limit_count,updated_at=now();

  return new;
end;
$$;

revoke all on function private.enforce_assisted_build_execution_gate() from public, anon, authenticated;

drop trigger if exists trg_assisted_build_execution_gate on public.factory_runs;
create trigger trg_assisted_build_execution_gate
before insert on public.factory_runs
for each row execute function private.enforce_assisted_build_execution_gate();
