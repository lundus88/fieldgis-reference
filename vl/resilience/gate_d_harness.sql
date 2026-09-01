create schema if not exists gate_d;
set search_path to gate_d, public;

create table gate_d.factory_runs (
  id text primary key,
  state text not null default 'building',
  target_environment text not null default 'staging',
  production_locked boolean not null default true
);

create table gate_d.runner_jobs (
  id uuid primary key default gen_random_uuid(),
  factory_run_id text not null unique references gate_d.factory_runs(id),
  state text not null default 'queued',
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  lease_token uuid,
  leased_at timestamptz,
  lease_expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function gate_d.claim_runner(p_runner text)
returns jsonb
language plpgsql
as $$
declare
  j gate_d.runner_jobs%rowtype;
  v_lease uuid := gen_random_uuid();
begin
  select * into j
  from gate_d.runner_jobs
  where (state='queued' or (state='leased' and lease_expires_at < now()))
    and attempts < max_attempts
  order by created_at
  for update skip locked
  limit 1;

  if not found then
    return jsonb_build_object('status','idle');
  end if;

  update gate_d.runner_jobs
  set state='leased', attempts=attempts+1, lease_token=v_lease,
      leased_at=now(), lease_expires_at=now()+interval '20 minutes', updated_at=now()
  where id=j.id
  returning * into j;

  if exists (
    select 1 from gate_d.factory_runs r
    where r.id=j.factory_run_id
      and (r.target_environment='production' or r.production_locked is distinct from true)
  ) then
    update gate_d.runner_jobs
    set state='failed', updated_at=now()
    where id=j.id;
    return jsonb_build_object('status','rejected','reason','production_execution_forbidden');
  end if;

  return jsonb_build_object(
    'status','leased',
    'job_id',j.id,
    'lease_token',j.lease_token,
    'attempt',j.attempts,
    'max_attempts',j.max_attempts,
    'runner',p_runner
  );
end;
$$;

create or replace function gate_d.complete_runner(
  p_job_id uuid,
  p_lease_token uuid,
  p_success boolean
)
returns jsonb
language plpgsql
as $$
declare
  j gate_d.runner_jobs%rowtype;
  v_run_state text;
begin
  select * into j
  from gate_d.runner_jobs
  where id=p_job_id
  for update;

  if not found then raise exception 'runner job not found'; end if;
  if j.state <> 'leased' or j.lease_token is distinct from p_lease_token then
    raise exception 'invalid runner lease';
  end if;
  if j.lease_expires_at < now() then
    raise exception 'runner lease expired';
  end if;

  if p_success then
    update gate_d.runner_jobs
    set state='succeeded', updated_at=now()
    where id=j.id;

    update gate_d.factory_runs
    set state='validating'
    where id=j.factory_run_id
      and target_environment <> 'production'
      and production_locked=true;
    v_run_state := 'validating';
  else
    if j.attempts < j.max_attempts then
      update gate_d.runner_jobs
      set state='queued', lease_token=null, leased_at=null, lease_expires_at=null, updated_at=now()
      where id=j.id;
      update gate_d.factory_runs set state='building' where id=j.factory_run_id;
      v_run_state := 'building';
    else
      update gate_d.runner_jobs set state='failed', updated_at=now() where id=j.id;
      update gate_d.factory_runs set state='failed' where id=j.factory_run_id;
      v_run_state := 'failed';
    end if;
  end if;

  return jsonb_build_object('status','recorded','factory_run_state',v_run_state);
end;
$$;

create table gate_d.external_actions (
  action_key text primary key,
  adapter_key text not null,
  created_at timestamptz not null default now()
);

create or replace function gate_d.record_external_action(p_action_key text, p_adapter_key text)
returns text
language plpgsql
as $$
declare
  v_count integer;
begin
  insert into gate_d.external_actions(action_key,adapter_key)
  values(p_action_key,p_adapter_key)
  on conflict(action_key) do nothing;
  get diagnostics v_count = row_count;
  if v_count=1 then return 'recorded'; end if;
  return 'duplicate';
end;
$$;

create table gate_d.adapters (
  adapter_key text primary key,
  available boolean not null default false
);

create or replace function gate_d.invoke_adapter(p_adapter_key text, p_action_key text)
returns jsonb
language plpgsql
as $$
declare
  v_available boolean;
  v_status text;
begin
  select available into v_available
  from gate_d.adapters
  where adapter_key=p_adapter_key;

  if coalesce(v_available,false) is distinct from true then
    return jsonb_build_object('status','blocked','retryable',true,'fail_closed',true);
  end if;

  v_status := gate_d.record_external_action(p_action_key,p_adapter_key);
  return jsonb_build_object('status',v_status,'retryable',false,'fail_closed',false);
end;
$$;

create table gate_d.usage_counters (
  account_id text not null,
  mode text not null check (mode in ('customer','founder')),
  metric_key text not null,
  window_start date not null,
  used_count bigint not null default 0,
  limit_count bigint not null,
  primary key(account_id,metric_key,window_start)
);

create table gate_d.usage_audit (
  id bigserial primary key,
  account_id text not null,
  mode text not null,
  metric_key text not null,
  amount bigint not null,
  override_used boolean not null,
  reason text,
  created_at timestamptz not null default now()
);

create or replace function gate_d.consume_usage(
  p_account_id text,
  p_mode text,
  p_metric_key text,
  p_amount bigint,
  p_override boolean default false,
  p_reason text default null
)
returns jsonb
language plpgsql
as $$
declare
  c gate_d.usage_counters%rowtype;
  v_next bigint;
  v_override_allowed boolean := false;
begin
  select * into c
  from gate_d.usage_counters
  where account_id=p_account_id
    and metric_key=p_metric_key
    and window_start=current_date
  for update;

  if not found then raise exception 'usage counter missing'; end if;
  if c.mode is distinct from p_mode then raise exception 'usage mode mismatch'; end if;

  v_next := c.used_count + p_amount;
  v_override_allowed := (
    p_mode='founder'
    and p_override=true
    and nullif(btrim(coalesce(p_reason,'')),'') is not null
  );

  if p_mode='customer' and p_override=true then
    return jsonb_build_object('status','blocked','reason','customer_override_forbidden','used_count',c.used_count);
  end if;

  if v_next > c.limit_count and not v_override_allowed then
    return jsonb_build_object('status','blocked','reason','rate_limit_exceeded','used_count',c.used_count);
  end if;

  update gate_d.usage_counters
  set used_count=v_next
  where account_id=p_account_id
    and metric_key=p_metric_key
    and window_start=current_date;

  insert into gate_d.usage_audit(account_id,mode,metric_key,amount,override_used,reason)
  values(p_account_id,p_mode,p_metric_key,p_amount,v_override_allowed,p_reason);

  return jsonb_build_object(
    'status','recorded',
    'used_count',v_next,
    'limit_count',c.limit_count,
    'override_used',v_override_allowed
  );
end;
$$;
