-- Evidence-bound VL certification-health writer.
-- This is not a synthetic heartbeat. It may refresh the authoritative health row
-- only when all five canonical builders have recent, complete, non-activating
-- certification results.
create or replace function private.refresh_vl_cert_health_from_builder_certifications()
returns jsonb
language plpgsql
security definer
volatile
set search_path=private,public,pg_temp
as $$
declare
  v_expected constant text[] := array[
    'web-react-v1',
    'pwa-react-v1',
    'mobile-flutter-v1',
    'gis-web-v1',
    'api-service-v1'
  ];
  v_count integer;
  v_bad integer;
  v_stale integer;
  v_authoritative_at timestamptz;
  v_oldest_at timestamptz;
begin
  perform pg_advisory_xact_lock(hashtext('vl_cert_health_evidence_refresh'));

  with latest as (
    select distinct on (builder_key)
      builder_key,
      decision,
      score,
      missing_evidence,
      distinct_run_count,
      evaluated_at,
      metadata
    from public.builder_certification_results
    where builder_key = any(v_expected)
    order by builder_key,evaluated_at desc
  )
  select
    count(*)::integer,
    count(*) filter (
      where lower(decision) <> 'certified'
         or score <> 1
         or distinct_run_count < 4
         or cardinality(missing_evidence) <> 0
         or coalesce((metadata->>'activation_requested')::boolean,false) is not false
    )::integer,
    count(*) filter (
      where evaluated_at < now() - interval '6 hours'
    )::integer,
    max(evaluated_at),
    min(evaluated_at)
  into v_count,v_bad,v_stale,v_authoritative_at,v_oldest_at
  from latest;

  if v_count <> cardinality(v_expected) then
    raise exception 'certification health refresh requires all five canonical builder results'
      using errcode='23514';
  end if;

  if v_bad <> 0 then
    raise exception 'certification health refresh blocked: latest builder certification is incomplete, non-certified, or activation-bearing'
      using errcode='23514';
  end if;

  if v_stale <> 0 then
    raise exception 'certification health refresh blocked: one or more builder certifications are older than six hours'
      using errcode='23514';
  end if;

  if v_authoritative_at is null or v_authoritative_at > now() + interval '1 minute' then
    raise exception 'certification health refresh blocked: invalid authoritative evidence timestamp'
      using errcode='23514';
  end if;

  insert into public.vl_cert_health(id,status,updated_at)
  values(1,'ok',v_authoritative_at)
  on conflict(id) do update
    set status=excluded.status,
        updated_at=excluded.updated_at;

  return jsonb_build_object(
    'status','ok',
    'updated_at',v_authoritative_at,
    'oldest_builder_evaluated_at',v_oldest_at,
    'builder_count',v_count,
    'distinct_run_floor',4,
    'max_builder_evidence_age_seconds',21600,
    'activation_requested',false,
    'source','builder_certification_results'
  );
end;
$$;

revoke all on function private.refresh_vl_cert_health_from_builder_certifications() from public,anon,authenticated;
grant execute on function private.refresh_vl_cert_health_from_builder_certifications() to service_role;

comment on function private.refresh_vl_cert_health_from_builder_certifications() is
'Evidence-bound certification health writer. Requires five recent certified builders, score 1, >=4 distinct runs, zero missing evidence and no activation request. Writes source evidence timestamp, never now().';
