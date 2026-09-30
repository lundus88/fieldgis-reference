-- Issue #433: preserve existing terminal failure and human-authority boundaries.
-- CREATE OR REPLACE retains the existing function privileges.
CREATE OR REPLACE FUNCTION public.complete_vrs_release_validation_job(p_job_id uuid, p_lease_token uuid, p_success boolean, p_gate_results jsonb DEFAULT '[]'::jsonb, p_result jsonb DEFAULT '{}'::jsonb, p_error_text text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'private', 'public', 'pg_temp'
AS $function$
declare
  j private.release_validation_jobs%rowtype; v_dep public.deployments%rowtype; v_required jsonb; r jsonb; v_missing int; v_fail int;
begin
  select * into j from private.release_validation_jobs where id=p_job_id for update;
  if not found then raise exception 'release validation job not found'; end if;
  if j.state<>'leased' or j.lease_token is distinct from p_lease_token then raise exception 'invalid release validation lease'; end if;
  if j.lease_expires_at<now() then raise exception 'release validation lease expired'; end if;
  select * into v_dep from public.deployments where id=j.deployment_id for update;
  if not found or v_dep.factory_run_id is distinct from j.factory_run_id then raise exception 'release validation deployment binding mismatch'; end if;
  v_required:=private.get_deployment_required_gates(j.deployment_id);
  if jsonb_array_length(v_required)=0 then raise exception 'deployment gate snapshot missing'; end if;

  if p_success then
    if jsonb_typeof(coalesce(p_gate_results,'[]'::jsonb))<>'array' then raise exception 'gate_results must be array'; end if;
    for r in select value from jsonb_array_elements(coalesce(p_gate_results,'[]'::jsonb)) loop
      if (r->>'key') in ('human_production_approval','production_lock') then raise exception 'human/production lock gates cannot be set by automated validator'; end if;
      if not exists(select 1 from jsonb_array_elements(v_required) g where g->>'key'=r->>'key') then raise exception 'validator returned gate not present in frozen deployment policy: %',r->>'key'; end if;
      if coalesce(r->>'status','') not in ('pass','fail') then raise exception 'automated gate status must be pass or fail'; end if;
      update public.release_gates set status=r->>'status',score=case when r ? 'score' then (r->>'score')::numeric else case when r->>'status'='pass' then 1 else 0 end end,evidence=coalesce(r->'evidence','{}'::jsonb),checked_at=now(),checked_by=null where factory_run_id=j.factory_run_id and gate_key=r->>'key';
    end loop;
    select count(*) into v_missing from jsonb_array_elements(v_required) g where not exists(select 1 from public.release_gates rg where rg.factory_run_id=j.factory_run_id and rg.gate_key=g->>'key' and rg.status='pass');
    select count(*) into v_fail from jsonb_array_elements(v_required) g where exists(select 1 from public.release_gates rg where rg.factory_run_id=j.factory_run_id and rg.gate_key=g->>'key' and rg.status='fail');
    if v_fail>0 then
      update private.release_validation_jobs set state='failed',result=coalesce(p_result,'{}'::jsonb),error_text='one or more technical release gates failed',finished_at=now(),updated_at=now() where id=j.id;
      update public.deployments set status='failed',certificate=certificate||jsonb_build_object('technical_validation','FAIL','validation_result',coalesce(p_result,'{}'::jsonb)) where id=j.deployment_id;
      update public.factory_runs set state='failed',error_text='Technical release validation failed',finished_at=now() where id=j.factory_run_id;
      update public.workflows w set state='failed',finished_at=now(),output=coalesce(w.output,'{}'::jsonb)||jsonb_build_object('technical_validation','FAIL') from public.factory_runs fr where fr.id=j.factory_run_id and w.id=fr.workflow_id;
      return jsonb_build_object('status','recorded','decision','technical_gates_failed','missing_or_failed',v_missing);
    elsif v_missing=0 then
      update private.release_validation_jobs set state='succeeded',result=coalesce(p_result,'{}'::jsonb),error_text=null,finished_at=now(),updated_at=now() where id=j.id;
      update public.deployments set status='certified',certificate=certificate||jsonb_build_object('technical_validation','PASS','validation_result',coalesce(p_result,'{}'::jsonb),'certified_at',now(),'gate_policy_version',gate_policy_version_snapshot,'gate_policy_sha256',gate_policy_sha256) where id=j.deployment_id;
      update public.factory_runs set state='awaiting_approval',result=coalesce(result,'{}'::jsonb)||jsonb_build_object('technical_certification','PASS'),error_text=null where id=j.factory_run_id and target_environment<>'production' and production_locked=true;
      update public.workflows w set state='waiting_approval',output=coalesce(w.output,'{}'::jsonb)||jsonb_build_object('technical_validation','PASS') from public.factory_runs fr where fr.id=j.factory_run_id and w.id=fr.workflow_id;
      return jsonb_build_object('status','recorded','decision','technically_certified','deployment_status','certified','factory_run_state','awaiting_approval','gate_policy_version',v_dep.gate_policy_version_snapshot,'gate_policy_sha256',v_dep.gate_policy_sha256);
    elsif j.attempts >= j.max_attempts then
      -- Use the existing terminal-failure path. Never certify missing evidence.
      return public.complete_vrs_release_validation_job(
        p_job_id, p_lease_token, false, '[]'::jsonb,
        coalesce(p_result,'{}'::jsonb) || jsonb_build_object('missing_gate_count',v_missing,'retry_exhausted',true),
        'Release validation attempts exhausted with required frozen gates still pending'
      );
    else
      update private.release_validation_jobs set state='queued',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'::jsonb),error_text='required frozen gates still pending',updated_at=now() where id=j.id;
      update public.factory_runs set state='validating',error_text=null where id=j.factory_run_id and state<>'failed';
      return jsonb_build_object('status','recorded','decision','more_validation_required','missing_or_failed',v_missing,'factory_run_state','validating');
    end if;
  else
    if j.attempts<j.max_attempts then
      update private.release_validation_jobs set state='queued',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,updated_at=now() where id=j.id;
      update public.factory_runs set state='validating',error_text=p_error_text where id=j.factory_run_id and state<>'failed';
      return jsonb_build_object('status','recorded','decision','retry_queued','factory_run_state','validating');
    else
      update private.release_validation_jobs set state='failed',result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,finished_at=now(),updated_at=now() where id=j.id;
      update public.deployments set status='failed',certificate=certificate||jsonb_build_object('technical_validation','FAIL','error',p_error_text) where id=j.deployment_id;
      update public.factory_runs set state='failed',error_text=coalesce(p_error_text,'Release validation failed'),finished_at=now() where id=j.factory_run_id;
      update public.workflows w set state='failed',finished_at=now(),output=coalesce(w.output,'{}'::jsonb)||jsonb_build_object('technical_validation','FAIL','error',p_error_text) from public.factory_runs fr where fr.id=j.factory_run_id and w.id=fr.workflow_id;
      return jsonb_build_object('status','recorded','decision','validation_failed','factory_run_state','failed');
    end if;
  end if;
end
$function$
;
