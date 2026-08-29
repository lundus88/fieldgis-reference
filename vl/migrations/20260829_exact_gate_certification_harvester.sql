-- Exact-match certification evidence harvesting for builders whose
-- certification evidence keys are directly produced by current release gates.
-- Intentionally excludes GIS and Mobile because their certification policies
-- contain stronger/different evidence semantics that must not be weakened.

create or replace function public.harvest_exact_release_gate_certification_evidence(
  p_factory_run_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path to 'public','private'
as $function$
declare
  v_run public.factory_runs%rowtype;
  v_dep public.deployments%rowtype;
  v_builder text;
  v_required text[];
  v_missing text[];
  v_inserted int := 0;
  v_result jsonb;
  r record;
begin
  select * into v_run from public.factory_runs where id=p_factory_run_id;
  if not found then raise exception 'factory run not found'; end if;

  select * into v_dep
  from public.deployments
  where factory_run_id=p_factory_run_id
  order by created_at desc
  limit 1;
  if not found then raise exception 'deployment not found'; end if;

  v_builder := v_dep.builder_key_snapshot;
  if v_builder not in ('web-react-v1','pwa-react-v1','api-service-v1') then
    raise exception 'builder % is not eligible for exact gate harvesting', v_builder;
  end if;

  if v_run.target_environment <> 'staging' or v_run.production_locked is not true then
    raise exception 'certification evidence requires staging + production_locked';
  end if;
  if v_run.state <> 'awaiting_approval' then
    raise exception 'factory run must be awaiting_approval, got %', v_run.state;
  end if;
  if v_dep.status <> 'certified' or v_dep.artifact_sha256 is null then
    raise exception 'deployment must be certified with immutable artifact sha';
  end if;
  if not exists (
    select 1 from public.release_gates
    where factory_run_id=p_factory_run_id
      and gate_key='supply_chain_attestation'
      and status='pass'
      and score=1
  ) then
    raise exception 'mandatory supply_chain_attestation is not PASS';
  end if;

  select coalesce(array_agg(value order by value),'{}'::text[])
  into v_required
  from public.builder_certification_policies p,
       lateral jsonb_array_elements_text(p.required_evidence)
  where p.builder_key=v_builder and p.status='active';

  if cardinality(v_required)=0 then
    raise exception 'no active certification evidence policy for %',v_builder;
  end if;

  select coalesce(array_agg(req order by req),'{}'::text[])
  into v_missing
  from unnest(v_required) req
  where not exists (
    select 1 from public.release_gates g
    where g.factory_run_id=p_factory_run_id
      and g.gate_key=req
      and g.status='pass'
      and g.score=1
  );

  if cardinality(v_missing)>0 then
    raise exception 'required exact-match release gates are not all PASS: %',v_missing;
  end if;

  for r in
    select g.id,g.gate_key,g.gate_type,g.score,g.evidence,g.checked_at
    from public.release_gates g
    where g.factory_run_id=p_factory_run_id
      and g.gate_key=any(v_required)
      and g.status='pass'
      and g.score=1
    order by g.gate_key
  loop
    if not exists (
      select 1 from public.builder_certification_evidence e
      where e.builder_key=v_builder
        and e.factory_run_id=p_factory_run_id
        and e.evidence_type=r.gate_key
        and e.evidence_status='pass'
    ) then
      insert into public.builder_certification_evidence(
        builder_key,factory_run_id,project_id,evidence_type,evidence_status,evidence,source_uri
      ) values (
        v_builder,
        p_factory_run_id,
        v_run.project_id,
        r.gate_key,
        'pass',
        jsonb_build_object(
          'source','certified_release_gate',
          'release_gate_id',r.id,
          'gate_type',r.gate_type,
          'gate_score',r.score,
          'gate_checked_at',r.checked_at,
          'artifact_sha256',v_dep.artifact_sha256,
          'gate_evidence',r.evidence,
          'supply_chain_required',true
        ),
        format('vl://release-gate/%s',r.id)
      );
      v_inserted := v_inserted + 1;
    end if;
  end loop;

  select public.evaluate_builder_certification(v_builder,false) into v_result;

  return jsonb_build_object(
    'ok',true,
    'factory_run_id',p_factory_run_id,
    'builder_key',v_builder,
    'inserted',v_inserted,
    'required_evidence',v_required,
    'certification',v_result
  );
end;
$function$;

revoke all on function public.harvest_exact_release_gate_certification_evidence(uuid) from public;
revoke all on function public.harvest_exact_release_gate_certification_evidence(uuid) from anon;
revoke all on function public.harvest_exact_release_gate_certification_evidence(uuid) from authenticated;
grant execute on function public.harvest_exact_release_gate_certification_evidence(uuid) to service_role;
