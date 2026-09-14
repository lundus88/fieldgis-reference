-- Read-only evidence query for the separately provisioned VL DEV database.
-- Does not invoke the release evaluator or create/update release-gate evidence.
begin read only;

select version() as database_version, current_database() as database_name;

select n.nspname as schema_name,p.proname,
       pg_get_function_identity_arguments(p.oid) as arguments,p.prosecdef,p.proconfig,
       has_function_privilege('public',p.oid,'EXECUTE') as public_execute,
       has_function_privilege('anon',p.oid,'EXECUTE') as anon_execute,
       has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_execute
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where (n.nspname='public' and p.proname in (
  'request_vrs_internal_usage_override','vl_get_assisted_build_quote','vl_prepare_assisted_build_product_alignment'
)) or (n.nspname='private' and p.proname in (
  'request_vrs_internal_usage_override_impl','build_assisted_build_product_alignment','validate_product_alignment'
))
order by n.nspname,p.proname;

-- Exact existing evaluator predicates, observed read-only on 2026-09-14.
select
  (select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
   where n.nspname='public' and c.relkind='r' and c.relrowsecurity=false)
    as public_tables_without_rls,
  (select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace
   where n.nspname='public' and p.prokind='f' and p.prosecdef
   and (has_function_privilege('public',p.oid,'EXECUTE')
        or has_function_privilege('anon',p.oid,'EXECUTE')
        or has_function_privilege('authenticated',p.oid,'EXECUTE')))
    as public_security_definer_exposed_to_client_roles;

select role_name,table_name,
       has_table_privilege(role_name,table_name,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') as table_access,
       has_any_column_privilege(role_name,table_name,'SELECT,INSERT,UPDATE,REFERENCES') as column_access
from unnest(array['anon','authenticated']) role_name
cross join unnest(array['private.internal_usage_overrides','private.internal_usage_audit',
                       'private.assisted_build_cost_policy']) table_name;

-- This GUC may be null when configured by PostgREST's environment. Null is not
-- evidence of non-exposure: separately verify private is rejected with PGRST106.
select current_setting('pgrst.db_schemas',true) as exposed_schema_setting;

rollback;
