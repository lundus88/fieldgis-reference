create table private.production_deployment_verifications (
  id uuid primary key default gen_random_uuid(),
  deployment_id uuid not null references public.deployments(id) on delete cascade,
  promotion_job_id uuid not null references private.production_promotion_jobs(id) on delete cascade,
  check_key text not null,
  expected jsonb not null,
  actual jsonb not null,
  status text not null check (status in ('pass','fail')),
  evidence jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now(),
  unique(promotion_job_id,check_key)
);

create table private.production_rollback_audits (
  id uuid primary key default gen_random_uuid(),
  deployment_id uuid not null references public.deployments(id),
  previous_deployment_id uuid references public.deployments(id),
  requested_by uuid references auth.users(id),
  state text not null check (state in ('blocked','pending','executing','succeeded','failed')),
  target_adapter text,
  provider_deployment_id text,
  artifact_sha256 text,
  reason text,
  evidence jsonb not null default '{}'::jsonb,
  requested_at timestamptz not null default now(),
  finished_at timestamptz
);

revoke all on private.production_deployment_verifications from public,anon,authenticated;
revoke all on private.production_rollback_audits from public,anon,authenticated;

create or replace function public.complete_vrs_production_promotion_job(
 p_job_id uuid,p_lease_token uuid,p_success boolean,p_result jsonb default '{}'::jsonb,p_error_text text default null
) returns jsonb language plpgsql security definer set search_path=private,public,pg_temp as $$
declare j private.production_promotion_jobs%rowtype; v_dep public.deployments%rowtype; v_sha text; v_checks jsonb; v_bad int;
begin
 select * into j from private.production_promotion_jobs where id=p_job_id for update;
 if not found then raise exception 'promotion job not found'; end if;
 if j.state<>'leased' or j.lease_token is distinct from p_lease_token then raise exception 'invalid promotion lease'; end if;
 if j.lease_expires_at<now() then raise exception 'promotion lease expired'; end if;
 select * into v_dep from public.deployments where id=j.deployment_id for update;
 if p_success then
   v_sha:=nullif(p_result->>'artifact_sha256','');
   if v_sha is null or lower(v_sha)<>lower(j.artifact_sha256) then raise exception 'promoted artifact SHA-256 mismatch'; end if;
   if p_result->>'post_deploy_verification'<>'PASS' then raise exception 'post-deploy verification PASS evidence required'; end if;
   if j.target_adapter<>'mobile-release-artifact' and nullif(p_result->>'provider_url','') is null then raise exception 'provider deployment reference required'; end if;
   v_checks:=coalesce(p_result->'verification_checks','[]'::jsonb);
   if jsonb_typeof(v_checks)<>'array' then raise exception 'verification_checks must be an array'; end if;
   if jsonb_array_length(v_checks)=0 then raise exception 'post-deploy verification checks required'; end if;
   select count(*) into v_bad from jsonb_array_elements(v_checks) c where lower(coalesce(c->>'status',''))<>'pass';
   if v_bad>0 then raise exception 'one or more post-deploy checks failed'; end if;
   insert into private.production_deployment_verifications(deployment_id,promotion_job_id,check_key,expected,actual,status,evidence,checked_at)
   select j.deployment_id,j.id,c->>'check_key',coalesce(c->'expected','null'),coalesce(c->'actual','null'),'pass',coalesce(c->'evidence','{}'),coalesce((c->>'timestamp')::timestamptz,now())
   from jsonb_array_elements(v_checks) c where nullif(c->>'check_key','') is not null
   on conflict(promotion_job_id,check_key) do update set expected=excluded.expected,actual=excluded.actual,status=excluded.status,evidence=excluded.evidence,checked_at=excluded.checked_at;
   update private.production_promotion_jobs set state='succeeded',result=coalesce(p_result,'{}'),error_text=null,finished_at=now(),updated_at=now() where id=j.id;
   update public.deployments set status='deployed',certificate=certificate||jsonb_build_object(
     'promotion','PASS','promotion_adapter',j.target_adapter,'promoted_artifact_sha256',v_sha,
     'provider_deployment_id',coalesce(p_result->>'provider_deployment_id',p_result->>'provider_url'),
     'provider_url',p_result->>'provider_url','post_deploy_verification','PASS',
     'promotion_result',coalesce(p_result,'{}'),'immutable_no_rebuild',true) where id=j.deployment_id;
   return jsonb_build_object('status','recorded','decision','promotion_succeeded','deployment_status','deployed','artifact_sha256',v_sha);
 else
   if j.attempts<j.max_attempts then
     update private.production_promotion_jobs set state='queued',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'),error_text=p_error_text,updated_at=now() where id=j.id;
     update public.deployments set status='approved',certificate=certificate||jsonb_build_object('promotion_retry',true,'last_error',p_error_text) where id=j.deployment_id;
     return jsonb_build_object('status','recorded','decision','retry_queued');
   end if;
   update private.production_promotion_jobs set state='failed',result=coalesce(p_result,'{}'),error_text=p_error_text,finished_at=now(),updated_at=now() where id=j.id;
   update public.deployments set status='failed',certificate=certificate||jsonb_build_object('promotion','FAIL','error',p_error_text,'rollback_state','pending') where id=j.deployment_id;
   return jsonb_build_object('status','recorded','decision','promotion_failed','rollback_state','pending');
 end if;
end $$;

revoke all on function public.complete_vrs_production_promotion_job(uuid,uuid,boolean,jsonb,text) from public,anon,authenticated;
grant execute on function public.complete_vrs_production_promotion_job(uuid,uuid,boolean,jsonb,text) to service_role;

create or replace function private.request_production_rollback(p_deployment_id uuid,p_reason text default null)
returns jsonb language plpgsql security definer set search_path=private,public,pg_temp as $$
declare v_uid uuid:=auth.uid(); d public.deployments%rowtype; prev public.deployments%rowtype; v_id uuid; v_adapter text;
begin
 if v_uid is null then raise exception 'authenticated user required'; end if;
 select * into d from public.deployments where id=p_deployment_id for update;
 if not found then raise exception 'deployment not found'; end if;
 if not private.has_project_role(d.project_id,array['owner','admin']) then raise exception 'owner/admin rollback authorization required'; end if;
 select * into prev from public.deployments x where x.project_id=d.project_id and x.id<>d.id and x.status in ('deployed','rolled_back')
   and x.certificate->>'technical_validation'='PASS' and x.artifact_sha256 is not null
   and coalesce(x.certificate->>'provider_deployment_id',x.certificate->>'provider_url') is not null
   order by x.deployed_at desc nulls last limit 1;
 if not found then
   insert into private.production_rollback_audits(deployment_id,requested_by,state,reason,evidence)
   values(d.id,v_uid,'blocked',coalesce(p_reason,'rollback requested'),'{"blocker":"previous certified provider deployment required"}') returning id into v_id;
   return jsonb_build_object('status','BLOCKED','rollback_audit_id',v_id,'reason','previous certified provider deployment required');
 end if;
 v_adapter:=coalesce(d.certificate->>'promotion_adapter',d.certificate#>>'{promotion,adapter}');
 insert into private.production_rollback_audits(deployment_id,previous_deployment_id,requested_by,state,target_adapter,provider_deployment_id,artifact_sha256,reason,evidence)
 values(d.id,prev.id,v_uid,'pending',v_adapter,coalesce(prev.certificate->>'provider_deployment_id',prev.certificate->>'provider_url'),prev.artifact_sha256,p_reason,
   jsonb_build_object('deterministic_target',true,'previous_release_version',prev.release_version,'history_preserved',true)) returning id into v_id;
 update public.deployments set certificate=certificate||jsonb_build_object('rollback_state','pending','rollback_audit_id',v_id,'rollback_target_deployment_id',prev.id) where id=d.id;
 return jsonb_build_object('status','PENDING','rollback_audit_id',v_id,'previous_deployment_id',prev.id,'artifact_sha256',prev.artifact_sha256);
end $$;

create or replace function public.request_vrs_production_rollback(p_deployment_id uuid,p_reason text default null)
returns jsonb language sql security invoker set search_path=private,public,pg_temp as $$ select private.request_production_rollback(p_deployment_id,p_reason) $$;
revoke all on function public.request_vrs_production_rollback(uuid,text) from public,anon;
grant execute on function public.request_vrs_production_rollback(uuid,text) to authenticated;

create or replace function private.enqueue_production_promotion_job() returns trigger language plpgsql security definer set search_path=private,public,pg_temp as $$
declare v_run public.factory_runs%rowtype; v_builder text; v_adapter text; v_configured boolean;
begin
 if new.status='approved' and (tg_op='INSERT' or old.status is distinct from new.status) then
   select * into v_run from public.factory_runs where project_id=new.project_id and workflow_id=new.workflow_id order by created_at desc limit 1;
   if not found then return new; end if;
   v_builder:=coalesce(v_run.result#>>'{runner,builder_key}',private.resolve_factory_builder(v_run.id));
   select adapter_key,configured into v_adapter,v_configured from private.production_adapter_registry where builder_key=v_builder;
   insert into private.production_promotion_jobs(deployment_id,project_id,factory_run_id,builder_key,artifact_sha256,target_adapter,state,error_text)
   values(new.id,new.project_id,v_run.id,v_builder,new.artifact_sha256,v_adapter,
     case when v_configured then 'queued' else 'blocked' end,
     case when v_configured then null else 'BLOCKED/UNCONFIGURED: production adapter target or credentials unavailable' end)
   on conflict(deployment_id) do nothing;
 end if;
 return new;
end $$;

create or replace view public.vl_factory_status with (security_invoker=true) as
select r.id factory_run_id,r.project_id,r.app_spec_id,r.workflow_id,r.input request_input,s.spec app_spec,
 coalesce(r.plan->>'builder_key',r.plan->>'selected_builder',r.result#>>'{runner,builder_key}') selected_builder,
 r.state factory_state,r.production_locked,r.target_environment,r.error_text factory_error,
 j.id runner_job_id,j.state runner_state,j.attempts runner_attempts,j.max_attempts runner_max_attempts,j.error_text runner_error,
 fa.id artifact_id,fa.name artifact_name,fa.sha256 artifact_sha256,fa.storage_path artifact_location,
 d.id deployment_id,d.release_version,d.status deployment_status,d.certificate,d.approved_by,d.deployed_at,
 coalesce((select jsonb_object_agg(g.gate_key,jsonb_build_object('status',g.status,'evidence',g.evidence,'checked_at',g.checked_at)) from public.release_gates g where g.factory_run_id=r.id),'{}') release_gates,
 a.id approval_id,a.status approval_status,a.decided_by,a.decided_at,
 p.id promotion_job_id,p.state promotion_state,p.attempts promotion_attempts,p.max_attempts promotion_max_attempts,p.target_adapter,p.error_text promotion_error,p.result promotion_result,
 ar.configured adapter_configured,ar.target_type adapter_target_type,ar.can_rollback,ar.can_health_check,
 r.created_at factory_created_at,r.finished_at factory_finished_at,j.created_at runner_created_at,j.finished_at runner_finished_at,fa.created_at artifact_created_at,d.created_at deployment_created_at,a.requested_at approval_requested_at,p.created_at promotion_created_at,p.finished_at promotion_finished_at,
 coalesce((select jsonb_agg(to_jsonb(v) order by v.checked_at) from private.production_deployment_verifications v where v.deployment_id=d.id),'[]') health_verification,
 coalesce((select jsonb_agg(to_jsonb(rb) order by rb.requested_at desc) from private.production_rollback_audits rb where rb.deployment_id=d.id),'[]') rollback_history,
 coalesce(p.error_text,j.error_text,r.error_text) current_error
from public.factory_runs r left join public.app_specs s on s.id=r.app_spec_id left join private.runner_jobs j on j.factory_run_id=r.id
left join lateral(select x.* from public.factory_artifacts x where x.factory_run_id=r.id order by x.created_at desc limit 1) fa on true
left join public.deployments d on d.workflow_id=r.workflow_id and d.project_id=r.project_id
left join public.approvals a on a.workflow_id=r.workflow_id and a.approval_type='production_release'
left join private.production_promotion_jobs p on p.deployment_id=d.id
left join private.production_adapter_registry ar on ar.builder_key=coalesce(r.plan->>'builder_key',r.plan->>'selected_builder',r.result#>>'{runner,builder_key}');
revoke all on public.vl_factory_status from public,anon,authenticated;
grant select on public.vl_factory_status to service_role;
