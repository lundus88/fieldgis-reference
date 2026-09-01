-- Assisted Build -> canonical vrs.product-alignment/1 preparation.
-- Generates reviewable traceability from customer interview data.
-- This does not approve, launch, certify, or promote production.

create or replace function private.build_assisted_build_product_alignment(
  p_answers jsonb,
  p_structured jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path=private,public,auth,extensions,pg_temp
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
    'founder_intent_hash',encode(digest(convert_to(v_fi::text,'UTF8'),'sha256'),'hex'),
    'certification_input_hash',encode(digest(convert_to(v_cert_input::text,'UTF8'),'sha256'),'hex')
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

revoke all on function private.build_assisted_build_product_alignment(jsonb,jsonb) from public, anon, authenticated;

create or replace function public.vl_prepare_assisted_build_product_alignment(
  p_answers jsonb,
  p_structured jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=private,public,auth,extensions,pg_temp
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
