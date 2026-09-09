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
