-- Issue #84: live Founder Intent -> User Requirement -> Acceptance Test enforcement.
-- New App Specs created after activation must carry spec.product_alignment.
-- Pre-existing App Specs remain legacy-compatible; internal certification-depth runs are exempt.

create table if not exists private.product_alignment_policy (
  policy_key text primary key,
  contract_version text not null,
  activated_at timestamptz not null,
  enabled boolean not null default true,
  constraint product_alignment_policy_key check (policy_key = 'default')
);

insert into private.product_alignment_policy(policy_key, contract_version, activated_at, enabled)
values ('default','vrs.product-alignment/1',clock_timestamp(),true)
on conflict (policy_key) do nothing;

create or replace function private.requires_product_alignment(p_app_spec_id uuid)
returns boolean
language sql
stable
set search_path = private, public, pg_temp
as $$
  select coalesce((
    select p.enabled and a.created_at >= p.activated_at
    from public.app_specs a
    cross join private.product_alignment_policy p
    where a.id = p_app_spec_id and p.policy_key='default'
  ), false)
$$;

create or replace function private.validate_product_alignment(p_alignment jsonb)
returns jsonb
language plpgsql
stable
set search_path = private, public, pg_temp
as $$
declare
  fi jsonb;
  reqs jsonb;
  tests jsonb;
  manifest jsonb;
  r jsonb;
  t jsonb;
  rid text;
  tid text;
  ref text;
  declared_test text;
begin
  if p_alignment is null or jsonb_typeof(p_alignment) <> 'object' then
    return jsonb_build_object('ok',false,'reason','product_alignment_missing');
  end if;

  fi := p_alignment->'founder_intent';
  reqs := p_alignment->'user_requirements';
  tests := p_alignment->'acceptance_tests';
  manifest := p_alignment->'traceability_manifest';

  if fi is null or jsonb_typeof(fi) <> 'object' then
    return jsonb_build_object('ok',false,'reason','founder_intent_missing');
  end if;

  if nullif(btrim(fi->>'primary_user'),'') is null
     or nullif(btrim(fi->>'core_problem'),'') is null
     or nullif(btrim(fi->>'desired_outcome'),'') is null
     or nullif(btrim(fi->>'success_metric'),'') is null
     or nullif(btrim(fi->>'commercial_model'),'') is null
     or nullif(btrim(fi->>'release_scope'),'') is null then
    return jsonb_build_object('ok',false,'reason','founder_intent_required_text_missing');
  end if;

  if jsonb_typeof(fi->'must_have') <> 'array' or jsonb_array_length(fi->'must_have') = 0
     or jsonb_typeof(fi->'must_not') <> 'array' or jsonb_array_length(fi->'must_not') = 0
     or jsonb_typeof(fi->'compliance_constraints') <> 'array' or jsonb_array_length(fi->'compliance_constraints') = 0
     or jsonb_typeof(fi->'human_decision_boundaries') <> 'array' or jsonb_array_length(fi->'human_decision_boundaries') = 0 then
    return jsonb_build_object('ok',false,'reason','founder_intent_required_array_missing');
  end if;

  if jsonb_typeof(reqs) <> 'array' or jsonb_array_length(reqs)=0 then
    return jsonb_build_object('ok',false,'reason','user_requirements_missing');
  end if;
  if jsonb_typeof(tests) <> 'array' or jsonb_array_length(tests)=0 then
    return jsonb_build_object('ok',false,'reason','acceptance_tests_missing');
  end if;

  if exists (
    select 1
    from jsonb_array_elements(reqs) q
    group by q->>'id'
    having nullif(btrim(q->>'id'),'') is null or count(*) > 1
  ) then
    return jsonb_build_object('ok',false,'reason','requirement_ids_invalid');
  end if;

  if exists (
    select 1
    from jsonb_array_elements(tests) x
    group by x->>'id'
    having nullif(btrim(x->>'id'),'') is null or count(*) > 1
  ) then
    return jsonb_build_object('ok',false,'reason','acceptance_test_ids_invalid');
  end if;

  for r in select value from jsonb_array_elements(reqs) loop
    rid := r->>'id';
    if nullif(btrim(r->>'user'),'') is null
       or nullif(btrim(r->>'context'),'') is null
       or nullif(btrim(r->>'expected_outcome'),'') is null
       or nullif(btrim(r->>'priority'),'') is null
       or jsonb_typeof(r->'intent_refs') <> 'array'
       or jsonb_array_length(r->'intent_refs') = 0 then
      return jsonb_build_object('ok',false,'reason','requirement_fields_missing','requirement_id',rid);
    end if;

    if jsonb_typeof(fi->'intent_ids')='array' then
      for ref in select value #>> '{}' from jsonb_array_elements(r->'intent_refs') loop
        if not (fi->'intent_ids' ? ref) then
          return jsonb_build_object('ok',false,'reason','unknown_founder_intent_ref','requirement_id',rid,'ref',ref);
        end if;
      end loop;
    end if;

    if r->>'priority'='P0' then
      if jsonb_typeof(r->'acceptance_test_ids') <> 'array' or jsonb_array_length(r->'acceptance_test_ids')=0 then
        return jsonb_build_object('ok',false,'reason','p0_acceptance_mapping_missing','requirement_id',rid);
      end if;
      for declared_test in select value #>> '{}' from jsonb_array_elements(r->'acceptance_test_ids') loop
        if not exists (
          select 1 from jsonb_array_elements(tests) x
          where x->>'id'=declared_test
            and jsonb_typeof(x->'requirement_ids')='array'
            and x->'requirement_ids' ? rid
        ) then
          return jsonb_build_object('ok',false,'reason','p0_mapping_not_bidirectional','requirement_id',rid,'test_id',declared_test);
        end if;
      end loop;
    end if;
  end loop;

  for t in select value from jsonb_array_elements(tests) loop
    tid := t->>'id';
    if jsonb_typeof(t->'requirement_ids') <> 'array' or jsonb_array_length(t->'requirement_ids')=0
       or nullif(btrim(t->>'observable_pass_condition'),'') is null then
      return jsonb_build_object('ok',false,'reason','acceptance_test_fields_missing','test_id',tid);
    end if;
    for rid in select value #>> '{}' from jsonb_array_elements(t->'requirement_ids') loop
      if not exists (select 1 from jsonb_array_elements(reqs) q where q->>'id'=rid) then
        return jsonb_build_object('ok',false,'reason','acceptance_test_unknown_requirement','test_id',tid,'requirement_id',rid);
      end if;
    end loop;
  end loop;

  if jsonb_typeof(p_alignment->'contradictions')='array' and exists (
    select 1 from jsonb_array_elements(p_alignment->'contradictions') c
    where coalesce(c->>'status','') <> 'resolved'
  ) then
    return jsonb_build_object('ok',false,'reason','unresolved_contradiction');
  end if;

  if manifest is null or jsonb_typeof(manifest) <> 'object'
     or nullif(btrim(manifest->>'founder_intent_hash'),'') is null
     or nullif(btrim(manifest->>'certification_input_hash'),'') is null then
    return jsonb_build_object('ok',false,'reason','traceability_manifest_incomplete');
  end if;

  return jsonb_build_object('ok',true,'contract_version','vrs.product-alignment/1');
end;
$$;

create or replace function private.enforce_product_alignment_on_factory_run()
returns trigger
language plpgsql
set search_path = private, public, pg_temp
as $$
declare
  v_alignment jsonb;
  v_result jsonb;
begin
  -- Internal builder certification-depth runs are governed separately and must remain operational.
  if coalesce((new.input->>'certification_depth_run')::boolean,false) then
    return new;
  end if;

  if private.requires_product_alignment(new.app_spec_id) then
    select a.spec->'product_alignment' into v_alignment
    from public.app_specs a where a.id=new.app_spec_id;
    v_result := private.validate_product_alignment(v_alignment);
    if coalesce((v_result->>'ok')::boolean,false) is distinct from true then
      raise exception 'product alignment gate rejected App Spec: %', coalesce(v_result->>'reason','invalid_product_alignment');
    end if;
    new.input := coalesce(new.input,'{}'::jsonb) || jsonb_build_object(
      'product_alignment_enforced',true,
      'product_alignment_contract','vrs.product-alignment/1'
    );
  end if;
  return new;
end;
$$;

drop trigger if exists trg_factory_runs_product_alignment on public.factory_runs;
create trigger trg_factory_runs_product_alignment
before insert on public.factory_runs
for each row execute function private.enforce_product_alignment_on_factory_run();

create or replace function public.claim_vrs_runner_job(p_runner_identity jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
set search_path to 'private','public','pg_temp'
as $function$
declare
  j private.runner_jobs%rowtype;
  v_lease uuid := gen_random_uuid();
  v_spec jsonb;
  v_artifacts jsonb;
  v_run public.factory_runs%rowtype;
  v_alignment_result jsonb;
begin
  select * into j
  from private.runner_jobs
  where (state='queued' or (state='leased' and lease_expires_at < now()))
    and attempts < max_attempts
  order by created_at
  for update skip locked
  limit 1;

  if not found then return jsonb_build_object('status','idle'); end if;

  update private.runner_jobs
  set state='leased', attempts=attempts+1, lease_token=v_lease,
      leased_at=now(), lease_expires_at=now()+interval '20 minutes',
      runner_identity=coalesce(p_runner_identity,'{}'::jsonb), updated_at=now()
  where id=j.id
  returning * into j;

  select * into v_run from public.factory_runs where id=j.factory_run_id;
  if v_run.target_environment='production' or v_run.production_locked is distinct from true then
    update private.runner_jobs set state='failed', error_text='production execution forbidden', finished_at=now(), updated_at=now() where id=j.id;
    return jsonb_build_object('status','rejected','reason','production_execution_forbidden');
  end if;

  select jsonb_build_object(
    'id',a.id,'title',a.title,'objective',a.objective,'spec',a.spec,
    'software_kind',a.software_kind,'target_platforms',a.target_platforms,'status',a.status
  ) into v_spec from public.app_specs a where a.id=v_run.app_spec_id;

  if coalesce((v_run.input->>'product_alignment_enforced')::boolean,false)
     or private.requires_product_alignment(v_run.app_spec_id) then
    v_alignment_result := private.validate_product_alignment(v_spec#>'{spec,product_alignment}');
    if coalesce((v_alignment_result->>'ok')::boolean,false) is distinct from true then
      update private.runner_jobs
      set state='failed', error_text='product alignment rejected: '||coalesce(v_alignment_result->>'reason','invalid_product_alignment'),
          finished_at=now(), updated_at=now()
      where id=j.id;
      update public.factory_runs
      set state='failed', error_text='product alignment gate rejected runner claim', finished_at=now()
      where id=j.factory_run_id;
      return jsonb_build_object('status','rejected','reason','product_alignment_rejected','detail',v_alignment_result);
    end if;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'path',g.path,'content',g.content,'sha256',g.sha256,'artifact_kind',g.artifact_kind,'metadata',g.metadata
  ) order by g.path),'[]'::jsonb)
  into v_artifacts
  from public.generated_artifacts g where g.factory_run_id=j.factory_run_id;

  return jsonb_build_object(
    'status','leased','job_id',j.id,'lease_token',v_lease,'factory_run_id',j.factory_run_id,
    'builder_key',j.builder_key,'attempt',j.attempts,'max_attempts',j.max_attempts,
    'app_spec',v_spec,'generated_artifacts',v_artifacts,
    'target_environment',v_run.target_environment,'production_locked',v_run.production_locked,
    'product_alignment_enforced',coalesce((v_run.input->>'product_alignment_enforced')::boolean,false)
  );
end;
$function$;

comment on function private.validate_product_alignment(jsonb) is
'Fail-closed DB validator for vrs.product-alignment/1. Mirrors the repository product-alignment contract at the execution boundary.';
