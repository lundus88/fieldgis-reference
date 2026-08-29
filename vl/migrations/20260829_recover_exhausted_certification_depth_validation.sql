create or replace function public.recover_exhausted_certification_depth_validation(p_factory_run_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'private','public','pg_temp'
as $function$
declare
  v_run public.factory_runs%rowtype;
  v_dep public.deployments%rowtype;
  v_job private.release_validation_jobs%rowtype;
  v_missing integer;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role required';
  end if;

  select * into v_run from public.factory_runs where id=p_factory_run_id for update;
  if not found
     or coalesce((v_run.input->>'certification_depth_run')::boolean,false) is distinct from true
     or v_run.target_environment <> 'staging'
     or v_run.production_locked is distinct from true
     or v_run.state <> 'validating' then
    raise exception 'factory run is not an eligible certification-depth validation';
  end if;

  select * into v_dep from public.deployments where factory_run_id=v_run.id for update;
  if not found or v_dep.status <> 'planned' then
    raise exception 'deployment is not planned';
  end if;

  select * into v_job from private.release_validation_jobs where deployment_id=v_dep.id for update;
  if not found or v_job.state <> 'queued' or v_job.attempts < v_job.max_attempts then
    raise exception 'validation job is not exhausted';
  end if;

  select count(*) into v_missing
  from jsonb_array_elements_text(v_dep.required_gates_snapshot) req(gate_key)
  left join public.release_gates g
    on g.factory_run_id=v_run.id and g.gate_key=req.gate_key
  where req.gate_key not in ('human_production_approval','production_lock')
    and coalesce(g.status,'pending') <> 'pass';

  if v_missing <> 0 then
    raise exception 'technical frozen gates are not all pass';
  end if;

  update private.release_validation_jobs
  set max_attempts=max_attempts+1,
      error_text='controlled certification-depth recovery after all technical frozen gates passed',
      updated_at=now()
  where id=v_job.id;

  return jsonb_build_object(
    'ok',true,
    'factory_run_id',v_run.id,
    'job_id',v_job.id,
    'attempts',v_job.attempts,
    'max_attempts',v_job.max_attempts+1,
    'scope','certification_depth_staging_only'
  );
end
$function$;

revoke all on function public.recover_exhausted_certification_depth_validation(uuid) from public, anon, authenticated;
grant execute on function public.recover_exhausted_certification_depth_validation(uuid) to service_role;
