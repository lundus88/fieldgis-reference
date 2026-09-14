-- Harden client-callable RPC boundaries without changing public RPC names or behavior.
-- Public RPCs become SECURITY INVOKER. Privileged table/function access remains in
-- narrowly-scoped private SECURITY DEFINER helpers. The private schema is not part
-- of the public Data API surface; authenticated already has schema USAGE and receives
-- EXECUTE only on these exact helpers.

begin;

-- -----------------------------------------------------------------------------
-- Founder/internal usage override
-- -----------------------------------------------------------------------------
create or replace function private.request_vrs_internal_usage_override_impl(
  p_project_id uuid,
  p_reason text,
  p_duration_minutes integer default 60
)
returns jsonb
language plpgsql
security definer
set search_path = private, public, auth, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_aal text := coalesce(auth.jwt()->>'aal','aal1');
  v_id uuid;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for internal usage override'; end if;
  if p_duration_minutes < 1 or p_duration_minutes > 240 then raise exception 'override duration outside 1..240 minutes'; end if;
  if length(btrim(coalesce(p_reason,''))) < 12 then raise exception 'override reason must be explicit'; end if;
  if not exists (
    select 1 from public.project_members pm
    where pm.project_id=p_project_id and pm.user_id=v_uid and pm.role in ('owner','admin')
  ) then raise exception 'owner/admin internal override authority required'; end if;

  insert into private.internal_usage_overrides(project_id,requested_by,reason,expires_at)
  values(p_project_id,v_uid,btrim(p_reason),now()+make_interval(mins=>p_duration_minutes))
  returning id into v_id;

  insert into private.internal_usage_audit(project_id,actor_user_id,event_type,reason,evidence)
  values(p_project_id,v_uid,'override_created',btrim(p_reason),jsonb_build_object(
    'override_id',v_id,'duration_minutes',p_duration_minutes,'aal',v_aal,
    'production_approval_changed',false,'production_promotion_changed',false
  ));

  return jsonb_build_object('ok',true,'override_id',v_id,'expires_in_minutes',p_duration_minutes,
    'production_approval_bypassed',false,'production_promotion_bypassed',false);
end;
$$;

revoke all on function private.request_vrs_internal_usage_override_impl(uuid,text,integer) from public, anon, authenticated;
grant execute on function private.request_vrs_internal_usage_override_impl(uuid,text,integer) to authenticated;

create or replace function public.request_vrs_internal_usage_override(
  p_project_id uuid,
  p_reason text,
  p_duration_minutes integer default 60
)
returns jsonb
language sql
security invoker
set search_path = private, public, auth, pg_temp
as $$
  select private.request_vrs_internal_usage_override_impl(p_project_id,p_reason,p_duration_minutes);
$$;
revoke all on function public.request_vrs_internal_usage_override(uuid,text,integer) from public, anon;
grant execute on function public.request_vrs_internal_usage_override(uuid,text,integer) to authenticated;

-- -----------------------------------------------------------------------------
-- Assisted Build quote
-- -----------------------------------------------------------------------------
create or replace function private.vl_get_assisted_build_quote_impl(p_complexity text)
returns jsonb
language plpgsql
security definer
set search_path = private, public, auth, pg_temp
as $$
declare
  v_policy private.assisted_build_cost_policy%rowtype;
begin
  if auth.uid() is null then
    raise exception 'authenticated user required' using errcode='42501';
  end if;

  select * into v_policy
  from private.assisted_build_cost_policy
  where complexity_class=p_complexity and enabled=true;

  if not found then
    raise exception 'assisted build cost policy unavailable' using errcode='P0001';
  end if;

  return jsonb_build_object(
    'complexity_class',v_policy.complexity_class,
    'factory_credit_estimate',v_policy.factory_credit_estimate,
    'service_tier_recommendation',v_policy.service_tier,
    'pricing_source','private.assisted_build_cost_policy',
    'commercial_amount',null,
    'production_payment_performed',false
  );
end;
$$;

revoke all on function private.vl_get_assisted_build_quote_impl(text) from public, anon, authenticated;
grant execute on function private.vl_get_assisted_build_quote_impl(text) to authenticated;

create or replace function public.vl_get_assisted_build_quote(p_complexity text)
returns jsonb
language sql
security invoker
set search_path = private, public, auth, pg_temp
as $$
  select private.vl_get_assisted_build_quote_impl(p_complexity);
$$;
revoke all on function public.vl_get_assisted_build_quote(text) from public, anon;
grant execute on function public.vl_get_assisted_build_quote(text) to authenticated;

-- -----------------------------------------------------------------------------
-- Assisted Build product-alignment preparation
-- -----------------------------------------------------------------------------
create or replace function private.vl_prepare_assisted_build_product_alignment_impl(
  p_answers jsonb,
  p_structured jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = private, public, auth, extensions, pg_temp
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

revoke all on function private.vl_prepare_assisted_build_product_alignment_impl(jsonb,jsonb) from public, anon, authenticated;
grant execute on function private.vl_prepare_assisted_build_product_alignment_impl(jsonb,jsonb) to authenticated;

create or replace function public.vl_prepare_assisted_build_product_alignment(
  p_answers jsonb,
  p_structured jsonb
)
returns jsonb
language sql
security invoker
set search_path = private, public, auth, extensions, pg_temp
as $$
  select private.vl_prepare_assisted_build_product_alignment_impl(p_answers,p_structured);
$$;
revoke all on function public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb) from public, anon;
grant execute on function public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb) to authenticated;

comment on function public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb) is
'Authenticated SECURITY INVOKER wrapper for Assisted Build product-alignment preparation. Privileged implementation is private and does not grant production authority.';

commit;
