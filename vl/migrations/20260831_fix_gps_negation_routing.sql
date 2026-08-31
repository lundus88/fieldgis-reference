-- Honor explicit negation for GPS/device-location requests.

create or replace function private.compile_app_request(p_prompt text)
returns jsonb
language plpgsql
set search_path to 'private','public','pg_temp'
as $function$
declare
  v_prompt text := lower(coalesce(p_prompt,''));
  v_builder_type text;
  v_target text;
  v_caps text[] := '{}';
  v_route jsonb;
  v_spec jsonb;
  v_title text;
  v_auth_requested boolean := false;
  v_database_requested boolean := false;
  v_gps_requested boolean := false;
  v_software_kind text;
begin
  if btrim(v_prompt) = '' then raise exception 'Prompt must not be empty'; end if;
  if v_prompt ~ '(pwa|progressive web app|installable web|installable website)' then
    v_builder_type := 'pwa'; v_target := 'pwa';
  elsif v_prompt ~ '(android|mobile|flutter|phone|telefon|smartphone)' then
    v_builder_type := 'mobile'; v_target := 'android';
  elsif v_prompt ~ '(gis|map|mapping|peta|maplibre|geojson|kml)' then
    v_builder_type := 'gis'; v_target := 'gis';
  elsif v_prompt ~ '(api|backend|endpoint|rest|webhook)' then
    v_builder_type := 'api'; v_target := 'api';
  elsif v_prompt ~ '(web|website|dashboard|portal|saas)' then
    v_builder_type := 'web'; v_target := 'web';
  else v_builder_type := null; v_target := null; end if;

  v_gps_requested := v_prompt ~ '(\mgps\M|\mgnss\M|current location|device location|live location|track(ing)? (my )?position|track(ing)? (my )?location|phone location|telefon.*lokasi|lokasi semasa|kedudukan semasa)'
    and v_prompt !~ '(no gps|without gps|gps (is )?not required|no gnss|without gnss|gnss (is )?not required|no device location|without device location|device location (is )?not required|no current location|without current location|current location (is )?not required|no live location|without live location|location tracking (is )?not required|do not track (my )?(position|location))';
  if v_gps_requested then v_caps := array_append(v_caps,'gps'); end if;

  if v_prompt ~ '(offline|tanpa internet|no internet)' then v_caps := array_append(v_caps,'offline'); end if;
  if v_prompt ~ '(installable|pwa|progressive web app)' then v_caps := array_append(v_caps,'installable'); end if;

  v_database_requested := v_prompt ~ '(supabase|database|database sync|sync|save history|history)'
    and v_prompt !~ '(no database|without database|no supabase|without supabase|database disabled|supabase disabled|no database entities|without database entities)';
  if v_database_requested then
    if v_builder_type='web' then v_caps := array_append(v_caps,'database');
    elsif v_builder_type='mobile' then v_caps := array_append(v_caps,'supabase');
    end if;
  end if;

  if v_prompt ~ '(camera|kamera|photo|gambar)' then v_caps := array_append(v_caps,'camera'); end if;
  if v_prompt ~ '(map|mapping|peta|maplibre)' then v_caps := array_append(v_caps,'map'); end if;
  if v_prompt ~ '(geojson)' then v_caps := array_append(v_caps,'geojson'); end if;
  if v_prompt ~ '(kml)' then v_caps := array_append(v_caps,'kml'); end if;
  if v_prompt ~ '(geospatial|spatial|gis)' then v_caps := array_append(v_caps,'geospatial'); end if;
  if v_prompt ~ '(rest)' then v_caps := array_append(v_caps,'rest'); end if;

  v_auth_requested := v_prompt ~ '(jwt|authentication|authenticated|auth|sign[ -]?in|login)'
    and v_prompt !~ '(no authentication|without authentication|no auth|without auth|authentication disabled|auth disabled)';
  if v_auth_requested then
    if v_builder_type='api' then v_caps := array_append(v_caps,'jwt');
    elsif v_builder_type in ('web','pwa') then v_caps := array_append(v_caps,'auth');
    end if;
  end if;

  select coalesce(array_agg(distinct x order by x),'{}'::text[]) into v_caps from unnest(v_caps) x;
  v_route := private.route_builder(v_builder_type,v_target,v_caps);
  v_title := left(regexp_replace(btrim(p_prompt),'\s+',' ','g'),120);
  v_software_kind := case v_builder_type
    when 'web' then 'web_app'
    when 'pwa' then 'pwa'
    when 'mobile' then 'mobile_app'
    when 'desktop' then 'desktop_app'
    when 'gis' then 'gis_app'
    when 'ai' then 'ai_app'
    when 'api' then 'api_service'
    else 'saas' end;
  v_spec := jsonb_build_object(
    'compiler_version','1.8',
    'source_prompt',p_prompt,
    'inferred',jsonb_build_object('builder_type',v_builder_type,'target',v_target,'required_capabilities',v_caps,'auth_requested',v_auth_requested,'database_requested',v_database_requested,'gps_requested',v_gps_requested),
    'routing',v_route,
    'selected_builder',v_route->'selected_builder',
    'governance',jsonb_build_object('status','draft','requires_human_approval',true,'auto_build_allowed',false)
  );
  insert into private.app_compiler_audit(prompt,inferred_builder_type,inferred_target,inferred_capabilities,routing_result,compiled_spec)
  values(p_prompt,v_builder_type,v_target,v_caps,v_route,v_spec);
  return jsonb_build_object(
    'title',v_title,
    'objective',p_prompt,
    'software_kind',v_software_kind,
    'target_platforms',case when v_target is null then jsonb_build_array() else jsonb_build_array(v_target) end,
    'status','draft',
    'spec',v_spec
  );
end;
$function$;
