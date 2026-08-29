-- Certification depth hardening:
-- a distinct run only counts toward minimum_distinct_runs when that run
-- contains PASS evidence for every required evidence type in the active policy.

create or replace function public.evaluate_builder_certification(
  p_builder_key text,
  p_activate boolean default false
)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  pol public.builder_certification_policies%rowtype;
  req text[];
  passed text[];
  missing text[];
  req_count int;
  pass_count int;
  run_count int;
  v_score numeric;
  v_decision text;
  v_status text;
begin
  select * into pol
  from public.builder_certification_policies
  where builder_key=p_builder_key and status='active';
  if not found then
    raise exception 'No active certification policy for builder %', p_builder_key;
  end if;

  select coalesce(array_agg(value order by value),'{}'::text[])
  into req
  from jsonb_array_elements_text(pol.required_evidence);

  select coalesce(array_agg(distinct evidence_type order by evidence_type),'{}'::text[])
  into passed
  from public.builder_certification_evidence
  where builder_key=p_builder_key
    and evidence_status='pass'
    and evidence_type = any(req);

  select coalesce(array_agg(x order by x),'{}'::text[])
  into missing
  from unnest(req) x
  where not (x = any(passed));

  req_count := cardinality(req);
  pass_count := cardinality(passed);

  -- IMPORTANT: depth is the number of COMPLETE runs, not runs containing
  -- merely one of the required evidence types.
  select count(*)::int
  into run_count
  from (
    select factory_run_id
    from public.builder_certification_evidence
    where builder_key=p_builder_key
      and evidence_status='pass'
      and factory_run_id is not null
      and evidence_type = any(req)
    group by factory_run_id
    having count(distinct evidence_type) = req_count
  ) complete_runs;

  v_score := case when req_count=0 then 0 else pass_count::numeric/req_count::numeric end;

  if cardinality(missing)=0
     and run_count >= pol.minimum_distinct_runs
     and v_score >= pol.minimum_score then
    v_decision := 'certified';
  elsif pass_count > 0 then
    v_decision := 'candidate';
  else
    v_decision := 'not_ready';
  end if;

  insert into public.builder_certification_results(
    builder_key,decision,score,passed_evidence,missing_evidence,distinct_run_count,metadata
  )
  values(
    p_builder_key,
    v_decision,
    v_score,
    passed,
    missing,
    run_count,
    jsonb_build_object(
      'policy_id',pol.id,
      'activation_requested',p_activate,
      'depth_semantics','complete_required_evidence_per_factory_run'
    )
  );

  if p_activate and v_decision='certified' and pol.allow_auto_activate then
    perform set_config('vrs.certification_activation','allow',true);
    update public.builder_registry
    set status='active',updated_at=now()
    where builder_key=p_builder_key and status <> 'active';
  end if;

  select status into v_status
  from public.builder_registry
  where builder_key=p_builder_key;

  return jsonb_build_object(
    'builder_key',p_builder_key,
    'decision',v_decision,
    'score',v_score,
    'passed_evidence',passed,
    'missing_evidence',missing,
    'distinct_run_count',run_count,
    'depth_semantics','complete_required_evidence_per_factory_run',
    'builder_status',v_status,
    'activated',(p_activate and v_decision='certified' and pol.allow_auto_activate)
  );
end;
$function$;
