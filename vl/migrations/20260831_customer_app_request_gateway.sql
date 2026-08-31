-- Authenticated VL Web app-request gateway.
-- The browser never calls this function directly. A verified Edge Function invokes it
-- with the service_role after validating the user's JWT and project membership.
-- SECURITY INVOKER is intentional: no privilege escalation inside this wrapper.

create or replace function public.vl_submit_customer_app_request(
  p_project_id uuid,
  p_user_id uuid,
  p_prompt text,
  p_title text default null,
  p_launch boolean default true
)
returns jsonb
language plpgsql
security invoker
set search_path to 'private', 'public', 'pg_temp'
as $function$
declare
  v_role text;
  v_compiled jsonb;
  v_app_spec_id uuid;
  v_version integer;
  v_launch jsonb;
  v_title text;
begin
  if p_project_id is null or p_user_id is null then
    raise exception 'project_id and user_id are required';
  end if;

  if char_length(btrim(coalesce(p_prompt,''))) < 20 then
    raise exception 'request must be at least 20 characters';
  end if;
  if char_length(p_prompt) > 10000 then
    raise exception 'request exceeds 10000 characters';
  end if;

  -- Serialize version allocation per project and prove the project exists.
  perform 1 from public.projects where id=p_project_id for update;
  if not found then raise exception 'project not found'; end if;

  select pm.role into v_role
  from public.project_members pm
  where pm.project_id=p_project_id and pm.user_id=p_user_id;

  if v_role not in ('owner','admin','builder') then
    raise exception 'project membership does not permit app requests';
  end if;

  v_compiled := private.compile_app_request(p_prompt);
  if coalesce(v_compiled #>> '{spec,selected_builder,builder_key}','') = '' then
    return jsonb_build_object(
      'decision','blocked',
      'reason','no_certified_builder_route',
      'production_locked',true,
      'compiled',v_compiled
    );
  end if;

  select coalesce(max(a.version),0)+1 into v_version
  from public.app_specs a where a.project_id=p_project_id;

  v_title := left(coalesce(nullif(btrim(p_title),''),v_compiled->>'title','Untitled app'),120);

  insert into public.app_specs(
    project_id,version,title,objective,spec,status,created_by,software_kind,target_platforms
  ) values (
    p_project_id,
    v_version,
    v_title,
    v_compiled->>'objective',
    v_compiled->'spec',
    'draft',
    p_user_id,
    coalesce(v_compiled->>'software_kind','saas'),
    coalesce(array(select jsonb_array_elements_text(coalesce(v_compiled->'target_platforms','[]'::jsonb))),'{}'::text[])
  ) returning id into v_app_spec_id;

  if p_launch then
    if v_role not in ('owner','admin') then
      return jsonb_build_object(
        'decision','draft_created',
        'reason','owner_or_admin_required_to_launch',
        'app_spec_id',v_app_spec_id,
        'production_locked',true
      );
    end if;
    v_launch := private.approve_and_launch_app_spec(v_app_spec_id,p_user_id);
    return jsonb_build_object(
      'decision','launched_to_staging',
      'app_spec_id',v_app_spec_id,
      'compiled',v_compiled,
      'launch',v_launch,
      'production_locked',true,
      'production_promotion','human_approval_required'
    );
  end if;

  return jsonb_build_object(
    'decision','draft_created',
    'app_spec_id',v_app_spec_id,
    'compiled',v_compiled,
    'production_locked',true
  );
end;
$function$;

revoke all on function public.vl_submit_customer_app_request(uuid,uuid,text,text,boolean) from public;
revoke all on function public.vl_submit_customer_app_request(uuid,uuid,text,text,boolean) from anon;
revoke all on function public.vl_submit_customer_app_request(uuid,uuid,text,text,boolean) from authenticated;
grant execute on function public.vl_submit_customer_app_request(uuid,uuid,text,text,boolean) to service_role;
