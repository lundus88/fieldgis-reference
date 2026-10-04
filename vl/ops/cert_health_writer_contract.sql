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
-- The human authorization producer is intentionally separate from this writer.
-- This file does not create approval authority or a public authorization endpoint.

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
