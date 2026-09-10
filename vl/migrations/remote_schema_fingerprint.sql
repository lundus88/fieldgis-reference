-- Read-only VL schema fingerprint query.
-- Purpose: compare a future canonical baseline / fresh DEV database with vrs-core
-- without copying production rows or changing migration history.

with
f as (
  select n.nspname as schema_name,
         p.proname,
         pg_get_function_identity_arguments(p.oid) as args,
         pg_get_functiondef(p.oid) as def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname in ('public','private')
),
c as (
  select table_schema,table_name,ordinal_position,column_name,data_type,udt_name,
         is_nullable,coalesce(column_default,'') as column_default
  from information_schema.columns
  where table_schema in ('public','private')
),
k as (
  select n.nspname as schema_name,cl.relname as table_name,con.conname,
         pg_get_constraintdef(con.oid,true) as def
  from pg_constraint con
  join pg_class cl on cl.oid=con.conrelid
  join pg_namespace n on n.oid=cl.relnamespace
  where n.nspname in ('public','private')
),
i as (
  select schemaname,tablename,indexname,indexdef
  from pg_indexes
  where schemaname in ('public','private')
),
p as (
  select schemaname,tablename,policyname,permissive,roles,cmd,
         coalesce(qual,'') qual,coalesce(with_check,'') with_check
  from pg_policies
  where schemaname in ('public','private')
),
h as (
  select version,name,
         encode(extensions.digest(coalesce(array_to_string(statements,E'\n'),'')::text,'sha256'),'hex') as sh
  from supabase_migrations.schema_migrations
),
hp as (
  select string_agg(version||'|'||name||'|'||sh,E'\n' order by version) as payload
  from h
)
select
  (select count(*) from h)::int as migration_count,
  (select min(version) from h) as first_migration,
  (select max(version) from h) as last_migration,
  encode(extensions.digest(coalesce((select payload from hp),'')::text,'sha256'),'hex') as migration_history_sha256,
  (select count(*) from f)::int as functions_count,
  encode(extensions.digest(coalesce((select string_agg(schema_name||'.'||proname||'('||args||')|'||def,E'\n' order by schema_name,proname,args) from f),'')::text,'sha256'),'hex') as functions_sha256,
  (select count(*) from c)::int as columns_count,
  encode(extensions.digest(coalesce((select string_agg(table_schema||'.'||table_name||'|'||ordinal_position||'|'||column_name||'|'||data_type||'|'||udt_name||'|'||is_nullable||'|'||column_default,E'\n' order by table_schema,table_name,ordinal_position) from c),'')::text,'sha256'),'hex') as columns_sha256,
  (select count(*) from k)::int as constraints_count,
  encode(extensions.digest(coalesce((select string_agg(schema_name||'.'||table_name||'|'||conname||'|'||def,E'\n' order by schema_name,table_name,conname) from k),'')::text,'sha256'),'hex') as constraints_sha256,
  (select count(*) from i)::int as indexes_count,
  encode(extensions.digest(coalesce((select string_agg(schemaname||'.'||tablename||'|'||indexname||'|'||indexdef,E'\n' order by schemaname,tablename,indexname) from i),'')::text,'sha256'),'hex') as indexes_sha256,
  (select count(*) from p)::int as policies_count,
  encode(extensions.digest(coalesce((select string_agg(schemaname||'.'||tablename||'|'||policyname||'|'||permissive||'|'||roles::text||'|'||cmd||'|'||qual||'|'||with_check,E'\n' order by schemaname,tablename,policyname) from p),'')::text,'sha256'),'hex') as policies_sha256;
