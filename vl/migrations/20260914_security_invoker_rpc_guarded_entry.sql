-- Issue #211. Additive RPC boundary hardening; no release gate or authority changes.
-- Keep private outside PostgREST's exposed schemas. See DATABASE_SECURITY_RPC_RC.md.
-- Apply after 20260914_public_security_definer_boundary.sql (merged PR #216).
begin;

-- PR #216 landed while this RC was being prepared. Preserve its historical SQL
-- and backend helper bodies, but close its client EXECUTE grants once the new
-- guarded entry paths below are installed in this same transaction. Conditional
-- lookup also permits applying this migration to the original incident schema.
do $$
declare
  v_signature text;
  v_function regprocedure;
begin
  foreach v_signature in array array[
    'private.request_vrs_internal_usage_override_impl(uuid,text,integer)',
    'private.vl_get_assisted_build_quote_impl(text)',
    'private.vl_prepare_assisted_build_product_alignment_impl(jsonb,jsonb)'
  ] loop
    v_function := to_regprocedure(v_signature);
    if v_function is not null then
      execute format('revoke all on function %s from public, anon, authenticated',v_function);
      execute format('alter function %s set search_path = %L',v_function,'');
    end if;
  end loop;
end;
$$;

-- An INVOKER facade cannot call a helper whose EXECUTE is revoked. Use a
-- transient INSERT interface: only the trigger owner can execute the privileged
-- helper. The view stores no rows and exposes no override/audit records.
create or replace view private.internal_usage_override_request
with (security_barrier = true, security_invoker = true) as
select null::uuid as project_id, null::text as reason,
       null::integer as duration_minutes, null::jsonb as result
where false;

revoke all on private.internal_usage_override_request from public, anon, authenticated;
-- Table-level REVOKE does not remove column grants on a replay.
revoke all (project_id, reason, duration_minutes, result)
  on private.internal_usage_override_request from public, anon, authenticated;
grant insert (project_id, reason, duration_minutes), select (result)
  on private.internal_usage_override_request to authenticated;
grant usage on schema private to authenticated;

create or replace function private.request_vrs_internal_usage_override_impl()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_aal text := coalesce(auth.jwt()->>'aal','aal1');
  v_id uuid;
begin
  if tg_op <> 'INSERT' or tg_table_schema <> 'private'
     or tg_table_name <> 'internal_usage_override_request' then
    raise exception 'invalid internal override entry point' using errcode='42501';
  end if;
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for internal usage override'; end if;
  if new.duration_minutes is null or new.duration_minutes < 1 or new.duration_minutes > 240 then
    raise exception 'override duration outside 1..240 minutes';
  end if;
  if length(btrim(coalesce(new.reason,''))) < 12 then raise exception 'override reason must be explicit'; end if;
  if not exists (
    select 1 from public.project_members pm
    where pm.project_id=new.project_id and pm.user_id=v_uid and pm.role in ('owner','admin')
  ) then raise exception 'owner/admin internal override authority required'; end if;

  insert into private.internal_usage_overrides(project_id,requested_by,reason,expires_at)
  values(new.project_id,v_uid,btrim(new.reason),now()+make_interval(mins=>new.duration_minutes))
  returning id into v_id;

  insert into private.internal_usage_audit(project_id,actor_user_id,event_type,reason,evidence)
  values(new.project_id,v_uid,'override_created',btrim(new.reason),jsonb_build_object(
    'override_id',v_id,'duration_minutes',new.duration_minutes,'aal',v_aal,
    'production_approval_changed',false,'production_promotion_changed',false
  ));

  new.result := jsonb_build_object('ok',true,'override_id',v_id,'expires_in_minutes',new.duration_minutes,
    'production_approval_bypassed',false,'production_promotion_bypassed',false);
  return new;
end;
$$;
revoke all on function private.request_vrs_internal_usage_override_impl() from public, anon, authenticated, service_role;

create or replace trigger trg_internal_usage_override_request
instead of insert on private.internal_usage_override_request
for each row execute function private.request_vrs_internal_usage_override_impl();

create or replace function public.request_vrs_internal_usage_override(
  p_project_id uuid,
  p_reason text,
  p_duration_minutes integer default 60
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_result jsonb;
begin
  if auth.uid() is null then raise exception 'authenticated user required'; end if;
  insert into private.internal_usage_override_request(project_id,reason,duration_minutes)
  values(p_project_id,p_reason,p_duration_minutes)
  returning result into v_result;
  if v_result is null then
    raise exception 'internal override result unavailable' using errcode='42501';
  end if;
  return v_result;
end;
$$;
revoke all on function public.request_vrs_internal_usage_override(uuid,text,integer) from public, anon;
grant execute on function public.request_vrs_internal_usage_override(uuid,text,integer) to authenticated;

-- Narrow read elevation through a private security-barrier projection, not a
-- client-executable SECURITY DEFINER helper or a grant on the raw policy table.
-- The view owner's read privilege is intentional: only the existing quote JSON
-- contract for enabled policies is readable. No mutation privileges are granted.
create or replace view private.assisted_build_quote_catalog
with (security_barrier = true, security_invoker = false) as
select policy.complexity_class,
       jsonb_build_object(
         'complexity_class',policy.complexity_class,
         'factory_credit_estimate',policy.factory_credit_estimate,
         'service_tier_recommendation',policy.service_tier,
         'pricing_source','private.assisted_build_cost_policy',
         'commercial_amount',null,
         'production_payment_performed',false
       ) as quote
from private.assisted_build_cost_policy policy
where policy.enabled=true and auth.uid() is not null;

revoke all on private.assisted_build_quote_catalog from public, anon, authenticated;
revoke all (complexity_class, quote) on private.assisted_build_quote_catalog from public, anon, authenticated;
grant select on private.assisted_build_quote_catalog to authenticated;

create or replace function public.vl_get_assisted_build_quote(p_complexity text)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
as $$
declare
  v_quote jsonb;
begin
  if auth.uid() is null then
    raise exception 'authenticated user required' using errcode='42501';
  end if;
  select quote into v_quote from private.assisted_build_quote_catalog
  where complexity_class=p_complexity;
  if not found then
    raise exception 'assisted build cost policy unavailable' using errcode='P0001';
  end if;
  return v_quote;
end;
$$;
revoke all on function public.vl_get_assisted_build_quote(text) from public, anon;
grant execute on function public.vl_get_assisted_build_quote(text) to authenticated;

-- Alignment generation/validation only transform caller-supplied JSON. They do
-- not require elevation. The generator body and SHA-256 output are retained;
-- pg_catalog.sha256 replaces pgcrypto digest(...,'sha256') so callers need no
-- new extension privileges and no writable schema is in the search path.

create or replace function private.build_assisted_build_product_alignment(
  p_answers jsonb,
  p_structured jsonb
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
as $$
declare
  v_problem text;
  v_primary_user text;
  v_current text;
  v_payments text;
  v_compliance text;
  v_features jsonb;
  v_feature text;
  v_fi jsonb;
  v_reqs jsonb := '[]'::jsonb;
  v_tests jsonb := '[]'::jsonb;
  v_rid text;
  v_tid text;
  v_i integer;
  v_manifest jsonb;
  v_cert_input jsonb;
begin
  if p_answers is null or jsonb_typeof(p_answers) <> 'object'
     or p_structured is null or jsonb_typeof(p_structured) <> 'object' then
    raise exception 'assisted build interview and structured draft required' using errcode='P0001';
  end if;

  v_problem := nullif(btrim(coalesce(p_answers->>'problem','')),'');
  v_primary_user := nullif(btrim(coalesce(p_answers->>'users','')),'');
  v_current := coalesce(nullif(btrim(coalesce(p_answers->>'current','')),''),'using the currently described workflow');
  v_payments := lower(coalesce(p_answers->>'payments','unknown'));
  v_compliance := nullif(btrim(coalesce(p_answers->>'compliance','')),'');
  v_features := p_structured->'required_features';

  if v_problem is null or v_primary_user is null then
    raise exception 'assisted build problem and primary user required for product alignment' using errcode='P0001';
  end if;
  if jsonb_typeof(v_features) <> 'array' or jsonb_array_length(v_features)=0 then
    raise exception 'assisted build required features missing for product alignment' using errcode='P0001';
  end if;

  v_fi := jsonb_build_object(
    'intent_ids',jsonb_build_array('FI-USER','FI-OUTCOME','FI-SAFETY','FI-COMMERCIAL'),
    'primary_user',v_primary_user,
    'core_problem',v_problem,
    'desired_outcome',coalesce(nullif(btrim(p_structured->>'proposed_workflow'),''),'Digitise the confirmed customer workflow with traceable requirements and governed release controls.'),
    'success_metric','All confirmed P0 required features are demonstrably usable by the primary user and every mapped acceptance test passes.',
    'commercial_model',case
      when v_payments='yes' then 'Payment-enabled application; paid fulfillment requires verified provider state and separately authorized commercial execution.'
      else 'Launch-pilot staging entitlement; commercial pricing and paid execution remain governed separately.'
    end,
    'release_scope','Assisted Build V1 staging build only; production release remains subject to explicit human production approval and governed promotion.',
    'must_have',v_features,
    'must_not',jsonb_build_array(
      'bypass explicit human production approval',
      'autonomously promote to production',
      'treat unverified payment state as paid',
      'silently discard unresolved interview assumptions'
    ),
    'compliance_constraints',jsonb_build_array(
      'staging execution remains production-locked',
      'customer data access remains scoped by authentication and authorization',
      'external provider actions remain subject to adapter readiness and verification'
    ) || case when v_compliance is not null then jsonb_build_array(v_compliance) else '[]'::jsonb end,
    'human_decision_boundaries',jsonb_build_array(
      'production approval',
      'production promotion',
      'commercial pricing or plan changes',
      'material legal or compliance wording changes'
    )
  );

  for v_i in 0..jsonb_array_length(v_features)-1 loop
    v_feature := nullif(btrim(v_features->>v_i),'');
    if v_feature is null then
      raise exception 'empty required feature cannot be aligned' using errcode='P0001';
    end if;
    v_rid := 'UR-' || lpad((v_i+1)::text,3,'0');
    v_tid := 'AT-' || lpad((v_i+1)::text,3,'0');

    v_reqs := v_reqs || jsonb_build_array(jsonb_build_object(
      'id',v_rid,
      'user',v_primary_user,
      'context',v_current,
      'expected_outcome',v_feature,
      'priority','P0',
      'intent_refs',jsonb_build_array('FI-OUTCOME','FI-SAFETY'),
      'acceptance_test_ids',jsonb_build_array(v_tid)
    ));

    v_tests := v_tests || jsonb_build_array(jsonb_build_object(
      'id',v_tid,
      'requirement_ids',jsonb_build_array(v_rid),
      'observable_pass_condition',format(
        'A permitted user can complete the requirement "%s" in staging and observe the resulting UI, state, or output without an unhandled error.',
        v_feature
      )
    ));
  end loop;

  v_cert_input := jsonb_build_object(
    'contract','vl.assisted-build/1',
    'answers',p_answers,
    'structured',p_structured,
    'user_requirements',v_reqs,
    'acceptance_tests',v_tests
  );

  v_manifest := jsonb_build_object(
    'founder_intent_hash',encode(pg_catalog.sha256(convert_to(v_fi::text,'UTF8')),'hex'),
    'certification_input_hash',encode(pg_catalog.sha256(convert_to(v_cert_input::text,'UTF8')),'hex')
  );

  return jsonb_build_object(
    'contract_version','vrs.product-alignment/1',
    'source','assisted_build_customer_interview',
    'founder_intent',v_fi,
    'user_requirements',v_reqs,
    'acceptance_tests',v_tests,
    'contradictions','[]'::jsonb,
    'traceability_manifest',v_manifest
  );
end;
$$;

revoke all on function private.build_assisted_build_product_alignment(jsonb,jsonb) from public, anon;
grant execute on function private.build_assisted_build_product_alignment(jsonb,jsonb) to authenticated, service_role;

alter function private.validate_product_alignment(jsonb) security invoker;
alter function private.validate_product_alignment(jsonb) set search_path = '';
revoke all on function private.validate_product_alignment(jsonb) from public, anon;
grant execute on function private.validate_product_alignment(jsonb) to authenticated, service_role;

create or replace function public.vl_prepare_assisted_build_product_alignment(
  p_answers jsonb,
  p_structured jsonb
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
as $$
declare
  v_alignment jsonb;
  v_validation jsonb;
begin
  if auth.uid() is null then
    raise exception 'authenticated user required' using errcode='42501';
  end if;

  v_alignment := private.build_assisted_build_product_alignment(p_answers,p_structured);
  v_validation := private.validate_product_alignment(v_alignment);
  if coalesce((v_validation->>'ok')::boolean,false) is distinct from true then
    raise exception 'generated assisted build product alignment invalid: %',coalesce(v_validation->>'reason','unknown') using errcode='P0001';
  end if;

  return v_alignment || jsonb_build_object(
    'validation',v_validation,
    'generated_for_review',true,
    'production_approval_performed',false,
    'production_promotion_performed',false
  );
end;
$$;

revoke all on function public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb) from public, anon;
grant execute on function public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb) to authenticated;

comment on function public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb) is
'Authenticated read-only preparation of canonical product-alignment evidence for Assisted Build review. No factory run or production authority mutation.';

-- Abort the transaction on unexpected inherited privileges. These checks are
-- not release evidence and do not write release_gates or approval records.
do $$
declare
  v_signature text;
  v_oid oid;
  v_role text;
  v_table text;
begin
  foreach v_signature in array array[
    'public.request_vrs_internal_usage_override(uuid,text,integer)',
    'public.vl_get_assisted_build_quote(text)',
    'public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb)'
  ] loop
    v_oid := v_signature::regprocedure;
    if (select prosecdef from pg_catalog.pg_proc where oid=v_oid)
       or has_function_privilege('public',v_oid,'EXECUTE')
       or has_function_privilege('anon',v_oid,'EXECUTE')
       or not has_function_privilege('authenticated',v_oid,'EXECUTE') then
      raise exception 'public RPC privilege boundary invalid: %',v_signature;
    end if;
  end loop;
  foreach v_role in array array['public','anon','authenticated'] loop
    if has_function_privilege(v_role,'private.request_vrs_internal_usage_override_impl()','EXECUTE') then
      raise exception 'privileged override helper must not be client-executable';
    end if;
    foreach v_signature in array array[
      'private.request_vrs_internal_usage_override_impl(uuid,text,integer)',
      'private.vl_get_assisted_build_quote_impl(text)',
      'private.vl_prepare_assisted_build_product_alignment_impl(jsonb,jsonb)'
    ] loop
      v_oid := to_regprocedure(v_signature);
      if v_oid is not null and has_function_privilege(v_role,v_oid,'EXECUTE') then
        raise exception 'legacy privileged helper unexpectedly client-executable: %',v_signature;
      end if;
    end loop;
    foreach v_table in array array[
      'private.internal_usage_overrides','private.internal_usage_audit','private.assisted_build_cost_policy'
    ] loop
      if has_table_privilege(v_role,v_table,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')
         or has_any_column_privilege(v_role,v_table,'SELECT,INSERT,UPDATE,REFERENCES') then
        raise exception 'raw private table unexpectedly accessible: % (%)',v_table,v_role;
      end if;
    end loop;
  end loop;
end;
$$;

commit;
