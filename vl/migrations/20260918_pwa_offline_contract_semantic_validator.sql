-- P0 RC: semantic offline-PWA release-gate hardening.
-- Development/review artifact only. Do not apply to Production without explicit human approval.
--
-- Problem:
-- evaluate_vrs_release_server_gates previously required the literal token "cache.put".
-- Valid service workers using another cache-handle variable such as "c.put(...)" were
-- falsely rejected even though they opened CacheStorage, wrote responses, and had an
-- offline caches.match fallback.
--
-- This successor keeps the same required signals but recognizes a bounded JavaScript
-- cache-handle .put(...) call independent of the local variable name.
-- No gate is removed and no Production authority is widened.

create or replace function public.evaluate_vrs_release_server_gates(p_factory_run_id uuid)
returns jsonb
language plpgsql
set search_path to 'private', 'public', 'extensions', 'pg_temp'
as $function$
declare
  v_required jsonb;
  v_run public.factory_runs%rowtype;
  v_dep public.deployments%rowtype;
  v_rls_off int;
  v_bad_definer int;
  v_artifact_match boolean;
  v_results jsonb:='[]'::jsonb;
  v_sw text;
  v_manifest text;
  v_pwa_cache_open boolean;
  v_pwa_cache_put boolean;
  v_pwa_cache_match boolean;
  v_pwa_offline_ok boolean;
begin
  select * into v_run from public.factory_runs where id=p_factory_run_id;
  if not found then raise exception 'factory run not found'; end if;

  select * into v_dep from public.deployments
   where factory_run_id=v_run.id and project_id=v_run.project_id
     and artifact_sha256=coalesce(v_run.result#>>'{runner,artifact_sha256}',v_run.result->>'artifact_sha256')
   order by created_at desc
   limit 1;
  if not found then raise exception 'release deployment not found for factory run'; end if;
  if v_dep.workflow_id is distinct from v_run.workflow_id then raise exception 'deployment workflow mismatch'; end if;

  v_required:=private.get_deployment_required_gates(v_dep.id);
  if v_required is null or jsonb_typeof(v_required) <> 'array' or jsonb_array_length(v_required)=0 then
    raise exception 'deployment required-gates snapshot missing or invalid';
  end if;

  if v_dep.builder_key_snapshot is null
     or v_dep.builder_version_snapshot is null
     or v_dep.gate_policy_version_snapshot is null
     or coalesce(v_dep.gate_policy_sha256,'')=''
     or coalesce(v_dep.app_spec_sha256,'')=''
     or coalesce(v_dep.builder_profile_sha256_snapshot,'')='' then
    raise exception 'deployment certification snapshot incomplete';
  end if;

  if exists(select 1 from jsonb_array_elements(v_required) g where g->>'key'='database_security') then
    select count(*) into v_rls_off from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and c.relrowsecurity=false;
    select count(*) into v_bad_definer from pg_proc p join pg_namespace n on n.oid=p.relnamespace
     where n.nspname='public' and p.prokind='f' and p.prosecdef
       and (has_function_privilege('public',p.oid,'EXECUTE') or has_function_privilege('anon',p.oid,'EXECUTE') or has_function_privilege('authenticated',p.oid,'EXECUTE'));
    update public.release_gates set status=case when v_rls_off=0 and v_bad_definer=0 then 'pass' else 'fail' end,
      score=case when v_rls_off=0 and v_bad_definer=0 then 1 else 0 end,
      evidence=jsonb_build_object('scope','vrs_control_plane_database','public_tables_without_rls',v_rls_off,'public_security_definer_exposed_to_client_roles',v_bad_definer,'checked_by','server_gate_evaluator','required_gates_authority','deployment_snapshot','deployment_id',v_dep.id),checked_at=now(),checked_by=null
      where factory_run_id=v_run.id and gate_key='database_security';
    v_results:=v_results||jsonb_build_array(jsonb_build_object('key','database_security','status',case when v_rls_off=0 and v_bad_definer=0 then 'pass' else 'fail' end));
  end if;

  if exists(select 1 from jsonb_array_elements(v_required) g where g->>'key'='rollback_contract') then
    select exists(select 1 from public.factory_artifacts fa where fa.factory_run_id=v_run.id and lower(fa.sha256)=lower(v_dep.artifact_sha256)) into v_artifact_match;
    update public.release_gates set status=case when v_run.production_locked=true and v_dep.status in ('planned','certified') and v_artifact_match then 'pass' else 'fail' end,
      score=case when v_run.production_locked=true and v_dep.status in ('planned','certified') and v_artifact_match then 1 else 0 end,
      evidence=jsonb_build_object('scope','control_plane_rollback_contract','immutable_artifact_hash_match',v_artifact_match,'production_lock_preserved',v_run.production_locked,'deployment_status',v_dep.status,'rollback_status_supported',true,'required_gates_authority','deployment_snapshot','deployment_id',v_dep.id,'note','External target rollback remains adapter-specific and is required before deployed state.'),checked_at=now(),checked_by=null
      where factory_run_id=v_run.id and gate_key='rollback_contract';
    v_results:=v_results||jsonb_build_array(jsonb_build_object('key','rollback_contract','status',case when v_run.production_locked=true and v_dep.status in ('planned','certified') and v_artifact_match then 'pass' else 'fail' end));
  end if;

  if exists(select 1 from jsonb_array_elements(v_required) g where g->>'key'='offline_pwa_contract') then
    select content into v_sw from public.generated_artifacts where factory_run_id=v_run.id and path='web/public/sw.js' order by created_at desc limit 1;
    select content into v_manifest from public.generated_artifacts where factory_run_id=v_run.id and path='web/public/manifest.webmanifest' order by created_at desc limit 1;

    v_pwa_cache_open := coalesce(v_sw,'') like '%caches.open%';
    v_pwa_cache_put := coalesce(v_sw,'') ~ '[A-Za-z_$][A-Za-z0-9_$]*[.]put[[:space:]]*[(]';
    v_pwa_cache_match := coalesce(v_sw,'') like '%caches.match%';

    v_pwa_offline_ok :=
      v_pwa_cache_open
      and v_pwa_cache_put
      and v_pwa_cache_match
      and coalesce(v_manifest,'') <> '';

    update public.release_gates set status=case when v_pwa_offline_ok then 'pass' else 'fail' end,
      score=case when v_pwa_offline_ok then 1 else 0 end,
      evidence=jsonb_build_object(
        'scope','generated_pwa_offline_contract',
        'manifest_present',coalesce(v_manifest,'')<>'',
        'cache_open',v_pwa_cache_open,
        'cache_put',v_pwa_cache_put,
        'cache_match',v_pwa_cache_match,
        'cache_put_detection','bounded_js_cache_handle_put_call',
        'checked_by','server_gate_evaluator',
        'required_gates_authority','deployment_snapshot',
        'deployment_id',v_dep.id
      ),checked_at=now(),checked_by=null
      where factory_run_id=v_run.id and gate_key='offline_pwa_contract';
    v_results:=v_results||jsonb_build_array(jsonb_build_object('key','offline_pwa_contract','status',case when v_pwa_offline_ok then 'pass' else 'fail' end));
  end if;

  return jsonb_build_object('factory_run_id',v_run.id,'deployment_id',v_dep.id,'required_gates_authority','deployment_snapshot','required_gates_snapshot',v_required,'server_gate_results',v_results);
end
$function$;

comment on function public.evaluate_vrs_release_server_gates(uuid) is
'VL release server-gate evaluator. Offline PWA gate requires manifest + CacheStorage open + bounded cache-handle put + caches.match fallback. Production application remains human-gated.';
