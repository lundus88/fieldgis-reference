-- Locked golden certification rerun authority.
-- Purpose: generate independent current-policy staging runs for active builders.
-- This authority cannot approve or promote production releases.

begin;

create table if not exists private.builder_certification_golden_profiles (
  builder_key text primary key references public.builder_registry(builder_key),
  project_name text not null,
  app_spec_title text,
  target_platforms text[] not null,
  max_batch_runs integer not null default 2 check (max_batch_runs between 1 and 2),
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into private.builder_certification_golden_profiles(builder_key,project_name,app_spec_title,target_platforms,max_batch_runs)
values
  ('web-react-v1','VL Golden Status Board','VL Golden Status Board',array['web'],2),
  ('pwa-react-v1','VL Golden PWA','VL Golden Field Checklist',array['pwa'],2),
  ('gis-web-v1','VL Golden GIS','VL Golden Map Viewer',array['gis'],2),
  ('api-service-v1','VL Golden API',null,array['api'],2),
  ('mobile-flutter-v1','FieldGIS Reference','FieldGIS Reference',array['android'],2)
on conflict(builder_key) do update set
  project_name=excluded.project_name,
  app_spec_title=excluded.app_spec_title,
  target_platforms=excluded.target_platforms,
  max_batch_runs=excluded.max_batch_runs,
  enabled=true,
  updated_at=now();

alter table private.builder_certification_golden_profiles enable row level security;
revoke all on private.builder_certification_golden_profiles from public, anon, authenticated;

create or replace function public.enqueue_vrs_golden_certification_runs(
  p_builder_key text,
  p_run_count integer default 1
)
returns jsonb
language plpgsql
security definer
set search_path = private, public, pg_temp
as $$
declare
  v_profile private.builder_certification_golden_profiles%rowtype;
  v_spec public.app_specs%rowtype;
  v_project public.projects%rowtype;
  v_builder public.builder_registry%rowtype;
  v_workflow_id uuid;
  v_run_id uuid;
  v_ids jsonb := '[]'::jsonb;
  v_actor uuid;
  i integer;
begin
  if current_user not in ('service_role','postgres') then
    raise exception 'service-role certification authority required';
  end if;

  select * into v_profile
  from private.builder_certification_golden_profiles
  where builder_key=p_builder_key and enabled=true;
  if not found then raise exception 'builder is not whitelisted for golden certification'; end if;

  if p_run_count is null or p_run_count < 1 or p_run_count > v_profile.max_batch_runs then
    raise exception 'run_count outside locked certification batch limit';
  end if;

  select * into v_builder from public.builder_registry
  where builder_key=p_builder_key and status='active';
  if not found then raise exception 'only active builders may use golden certification rerun authority'; end if;

  select p.* into v_project
  from public.projects p
  where p.name=v_profile.project_name
  order by p.created_at desc
  limit 1;
  if not found then raise exception 'whitelisted golden project not found'; end if;

  select a.* into v_spec
  from public.app_specs a
  where a.project_id=v_project.id
    and a.status='approved'
    and (v_profile.app_spec_title is null or a.title=v_profile.app_spec_title)
    and (
      p_builder_key='mobile-flutter-v1'
      or coalesce(a.spec #>> '{selected_builder,builder_key}',a.spec #>> '{routing,selected_builder,builder_key}')=p_builder_key
    )
  order by a.approved_at desc nulls last,a.created_at desc
  limit 1;
  if not found then raise exception 'approved whitelisted golden app spec not found'; end if;

  v_actor:=coalesce(v_spec.approved_by,v_spec.created_by);
  if v_actor is null then raise exception 'golden spec has no accountable actor'; end if;
  if not exists (
    select 1 from public.project_members pm
    where pm.project_id=v_project.id and pm.user_id=v_actor and pm.role in ('owner','admin','builder')
  ) then raise exception 'golden spec actor is not an authorized project member'; end if;

  if not exists (
    select 1 from public.environments e
    where e.project_id=v_project.id and e.kind='production' and e.status='ready'
  ) then raise exception 'ready production environment metadata required for release-candidate verification'; end if;

  for i in 1..p_run_count loop
    insert into public.workflows(project_id,app_spec_id,workflow_type,state,input,created_by)
    values(
      v_project.id,v_spec.id,'factory_build_v2','queued',
      jsonb_build_object(
        'builder_key',p_builder_key,
        'target_environment','staging',
        'target_platforms',to_jsonb(v_profile.target_platforms),
        'certification_depth_run',true,
        'certification_batch_index',i,
        'production_locked',true
      ),v_actor
    ) returning id into v_workflow_id;

    insert into public.factory_runs(
      project_id,app_spec_id,workflow_id,requested_by,run_type,state,
      target_environment,production_locked,input,plan,target_platforms
    ) values (
      v_project.id,v_spec.id,v_workflow_id,v_actor,'build','planning',
      'staging',true,
      jsonb_build_object(
        'builder_key',p_builder_key,
        'generator_version','certification-depth-v1',
        'certification_depth_run',true,
        'certification_batch_index',i
      ),
      jsonb_build_object(
        'purpose','current-policy-certification-depth',
        'builder_key',p_builder_key,
        'builders',jsonb_build_array(jsonb_build_object('key',p_builder_key))
      ),
      v_profile.target_platforms
    ) returning id into v_run_id;

    v_ids:=v_ids || jsonb_build_array(jsonb_build_object(
      'factory_run_id',v_run_id,
      'workflow_id',v_workflow_id,
      'builder_key',p_builder_key,
      'target_environment','staging',
      'production_locked',true
    ));
  end loop;

  return jsonb_build_object(
    'ok',true,
    'builder_key',p_builder_key,
    'run_count',p_run_count,
    'runs',v_ids,
    'production_locked',true,
    'production_approval_performed',false,
    'production_promotion_performed',false
  );
end;
$$;

revoke all on function public.enqueue_vrs_golden_certification_runs(text,integer) from public,anon,authenticated;
grant execute on function public.enqueue_vrs_golden_certification_runs(text,integer) to service_role;

commit;
