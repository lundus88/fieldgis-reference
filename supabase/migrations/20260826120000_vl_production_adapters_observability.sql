alter table private.production_adapter_registry add column if not exists builder_key text;
alter table private.production_adapter_registry add column if not exists configured boolean not null default false;
alter table private.production_adapter_registry add column if not exists target_type text;
alter table private.production_adapter_registry add column if not exists required_credentials jsonb not null default '[]'::jsonb;
alter table private.production_adapter_registry add column if not exists can_deploy boolean not null default false;
alter table private.production_adapter_registry add column if not exists can_rollback boolean not null default false;
alter table private.production_adapter_registry add column if not exists can_health_check boolean not null default false;
alter table private.production_adapter_registry add column if not exists configuration jsonb not null default '{}'::jsonb;

update private.production_adapter_registry set builder_key=case adapter_key
 when 'mobile-release-artifact' then 'mobile-flutter-v1' when 'vercel-web' then 'web-react-v1'
 when 'vercel-pwa' then 'pwa-react-v1' when 'vercel-gis' then 'gis-web-v1'
 when 'supabase-edge' then 'api-service-v1' else builder_key end,
 target_type=coalesce(target_type,target_kind), configured=(status='active'),
 can_deploy=coalesce((capabilities->>'live_deploy')::boolean,(capabilities->>'immutable_artifact')::boolean,false),
 can_rollback=coalesce((capabilities->>'rollback')::boolean,false),
 can_health_check=coalesce((capabilities->>'health_check')::boolean,false);

alter table private.production_adapter_registry alter column builder_key set not null;
alter table private.production_adapter_registry alter column target_type set not null;
create unique index if not exists production_adapter_registry_builder_key_uidx on private.production_adapter_registry(builder_key);

insert into private.production_adapter_registry
  (builder_key,adapter_key,target_kind,status,capabilities,configured,target_type,required_credentials,can_deploy,can_rollback,can_health_check,configuration)
values
  ('mobile-flutter-v1','mobile-release-artifact','mobile','active','{"immutable_artifact":true}',true,'android_distribution_artifact','[]',true,true,true,
   '{"immutable":true,"verification":["artifact_exists","sha256_match","release_metadata_exists"]}'),
  ('web-react-v1','vercel-production','web','unavailable','{"live_deploy":false,"immutable_artifact":true}',false,'vercel_production','["VERCEL_TOKEN","VERCEL_ORG_ID","VERCEL_PROJECT_ID"]',true,true,true,
   '{"promotion_mode":"prebuilt_or_existing_deployment","verification":["http_status","app_boot","critical_assets"]}'),
  ('pwa-react-v1','vercel-pwa-production','pwa','unavailable','{"live_deploy":false,"immutable_artifact":true}',false,'vercel_production','["VERCEL_TOKEN","VERCEL_ORG_ID","VERCEL_PROJECT_ID"]',true,true,true,
   '{"promotion_mode":"prebuilt_or_existing_deployment","verification":["http_status","app_boot","manifest","service_worker"]}'),
  ('gis-web-v1','vercel-gis-production','gis','unavailable','{"live_deploy":false,"immutable_artifact":true}',false,'vercel_production','["VERCEL_TOKEN","VERCEL_ORG_ID","VERCEL_PROJECT_ID"]',true,true,true,
   '{"promotion_mode":"prebuilt_or_existing_deployment","verification":["http_status","app_boot","maplibre_runtime"]}'),
  ('api-service-v1','supabase-edge-function','api','unavailable','{"live_deploy":false,"immutable_artifact":true}',false,'supabase_edge_function','["SUPABASE_ACCESS_TOKEN","SUPABASE_PROJECT_REF","SUPABASE_FUNCTION_NAME"]',true,true,true,
   '{"verification":["health_endpoint","jwt_contract","response_contract"]}')
on conflict (builder_key) do update set
  adapter_key=excluded.adapter_key,target_type=excluded.target_type,
  required_credentials=excluded.required_credentials,can_deploy=excluded.can_deploy,
  can_rollback=excluded.can_rollback,can_health_check=excluded.can_health_check,
  configuration=excluded.configuration,configured=excluded.configured,updated_at=now();

create or replace view public.production_adapter_status
with (security_invoker=true) as
select builder_key,adapter_key,configured,target_type,required_credentials,
       can_deploy,can_rollback,can_health_check,configuration,updated_at,
       case when configured then 'configured' else 'unconfigured' end as status
from private.production_adapter_registry;

revoke all on private.production_adapter_registry from public, anon, authenticated;
revoke all on public.production_adapter_status from public, anon, authenticated;
grant select on public.production_adapter_status to service_role;

create or replace view public.vl_factory_status
with (security_invoker=true) as
select r.id as factory_run_id,r.project_id,r.app_spec_id,r.workflow_id,
       r.input as request_input,s.spec as app_spec,r.plan->>'builder_key' as selected_builder,
       r.state as factory_state,r.production_locked,r.target_environment,r.error_text as factory_error,
       j.id as runner_job_id,j.state as runner_state,j.attempts as runner_attempts,j.max_attempts as runner_max_attempts,j.error_text as runner_error,
       fa.id as artifact_id,fa.name as artifact_name,fa.sha256 as artifact_sha256,fa.storage_path as artifact_location,
       d.id as deployment_id,d.release_version,d.status as deployment_status,d.certificate,d.approved_by,d.deployed_at,
       coalesce((select jsonb_object_agg(g.gate_key,jsonb_build_object('status',g.status,'evidence',g.evidence,'checked_at',g.checked_at)) from public.release_gates g where g.factory_run_id=r.id),'{}') as release_gates,
       a.id as approval_id,a.status as approval_status,a.decided_by,a.decided_at,
       p.id as promotion_job_id,p.state as promotion_state,p.attempts as promotion_attempts,p.max_attempts as promotion_max_attempts,p.target_adapter,p.error_text as promotion_error,p.result as promotion_result,
       ar.configured as adapter_configured,ar.target_type as adapter_target_type,ar.can_rollback,ar.can_health_check
from public.factory_runs r
left join public.app_specs s on s.id=r.app_spec_id
left join private.runner_jobs j on j.factory_run_id=r.id
left join lateral (select x.* from public.factory_artifacts x where x.factory_run_id=r.id order by x.created_at desc limit 1) fa on true
left join public.deployments d on d.workflow_id=r.workflow_id and d.project_id=r.project_id
left join public.approvals a on a.workflow_id=r.workflow_id and a.approval_type='production_release'
left join private.production_promotion_jobs p on p.deployment_id=d.id
left join private.production_adapter_registry ar on ar.builder_key=r.plan->>'builder_key';

revoke all on public.vl_factory_status from public, anon, authenticated;
grant select on public.vl_factory_status to service_role;

comment on view public.vl_factory_status is 'Authoritative service-role-only lifecycle status for the VL Command Centre.';
comment on table private.production_adapter_registry is 'Fail-closed production adapter capabilities and configuration state.';
