-- VL canonical schema baseline bootstrap — DEV/ephemeral environments only.
-- Source: authoritative schema capture 2026-10-04.
-- NEVER apply this file to Production.
-- It intentionally replaces only the application schemas public/private.
-- It does not copy runtime rows, approvals, deployments, certification evidence, or health state.

DROP SCHEMA IF EXISTS private CASCADE;
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public AUTHORIZATION postgres;
CREATE SCHEMA private AUTHORIZATION postgres;
COMMENT ON SCHEMA public IS 'standard public schema';




SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "private";


ALTER SCHEMA "private" OWNER TO "postgres";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "http" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "private"."acp_admin_event_id"("p_action_id" "text", "p_event_type" "text") RETURNS "text"
    LANGUAGE "sql" IMMUTABLE
    SET "search_path" TO 'pg_catalog', 'extensions'
    AS $$
  select 'acp:' || encode(
    extensions.digest(convert_to(p_action_id || '|' || p_event_type, 'UTF8'), 'sha256'),
    'hex'
  );
$$;


ALTER FUNCTION "private"."acp_admin_event_id"("p_action_id" "text", "p_event_type" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."acp_append_admin_audit_event"("p_action_id" "text", "p_event_type" "text", "p_capability" "text", "p_scope" "jsonb", "p_input_digest" "text", "p_decision" "text", "p_reason_code" "text", "p_execution_status" "text", "p_result_digest" "text", "p_metadata" "jsonb", "p_actor_evidence" "jsonb") RETURNS "text"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'pg_catalog', 'private', 'extensions'
    AS $_$
declare
  v_event_id text;
  v_existing private.agent_control_audit_events%rowtype;
  v_prior_seq integer;
  v_prior_digest text;
  v_next_seq integer;
  v_recorded_at timestamptz := clock_timestamp();
  v_requester jsonb;
  v_metadata jsonb;
  v_payload jsonb;
  v_event_digest text;
begin
  perform private.acp_assert_actor_evidence(p_actor_evidence);

  if p_action_id is null or length(p_action_id) < 16 or length(p_action_id) > 160 then
    raise exception 'ACP action_id invalid';
  end if;
  if p_input_digest !~ '^sha256:[a-f0-9]{64}$' then
    raise exception 'ACP input digest invalid';
  end if;
  if jsonb_typeof(p_metadata) <> 'object' then
    raise exception 'ACP audit metadata must be object';
  end if;
  if p_metadata::text ~* '(authorization|access_token|refresh_token|service_role_key|supabase_service_role_key|api_key|password|private_key|bearer_token|github_token|actions_id_token_request_token)' then
    raise exception 'ACP audit metadata contains forbidden credential field';
  end if;

  v_event_id := private.acp_admin_event_id(p_action_id, p_event_type);
  v_metadata := p_metadata || jsonb_build_object('actor_evidence', p_actor_evidence);
  perform pg_advisory_xact_lock(hashtextextended(p_action_id, 0));

  select * into v_existing
  from private.agent_control_audit_events
  where event_id = v_event_id;

  if found then
    if v_existing.action_id = p_action_id
       and v_existing.event_type = p_event_type
       and v_existing.capability = p_capability
       and v_existing.scope = p_scope
       and v_existing.input_digest = p_input_digest
       and v_existing.decision is not distinct from p_decision
       and v_existing.reason_code is not distinct from p_reason_code
       and v_existing.execution_status is not distinct from p_execution_status
       and v_existing.result_digest is not distinct from p_result_digest
       and v_existing.metadata = v_metadata then
      return v_existing.event_digest;
    end if;
    raise exception 'ACP deterministic audit event conflicts with existing evidence';
  end if;

  select event_seq, event_digest
    into v_prior_seq, v_prior_digest
  from private.agent_control_audit_events
  where action_id = p_action_id
  order by event_seq desc
  limit 1;

  v_next_seq := coalesce(v_prior_seq, 0) + 1;
  v_requester := jsonb_build_object(
    'agent_id', 'github-actions',
    'agent_version', '1',
    'role', 'acp-admin-workflow',
    'principal_type', 'system'
  );

  v_payload := jsonb_build_object(
    'schema_version', '1.0',
    'event_id', v_event_id,
    'action_id', p_action_id,
    'event_seq', v_next_seq,
    'event_type', p_event_type,
    'recorded_at', v_recorded_at,
    'requester', v_requester,
    'delegator_chain', '[]'::jsonb,
    'capability', p_capability,
    'scope', p_scope,
    'input_digest', p_input_digest,
    'decision', p_decision,
    'reason_code', p_reason_code,
    'execution_status', p_execution_status,
    'result_digest', p_result_digest,
    'previous_event_digest', v_prior_digest,
    'metadata', v_metadata
  );

  v_event_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_payload::text, 'UTF8'), 'sha256'),
    'hex'
  );

  insert into private.agent_control_audit_events (
    event_id, schema_version, action_id, event_seq, event_type, recorded_at,
    requester, delegator_chain, capability, scope, input_digest, decision,
    reason_code, execution_status, result_digest, previous_event_digest,
    event_digest, metadata
  ) values (
    v_event_id, '1.0', p_action_id, v_next_seq, p_event_type, v_recorded_at,
    v_requester, '[]'::jsonb, p_capability, p_scope, p_input_digest, p_decision,
    p_reason_code, p_execution_status, p_result_digest, v_prior_digest,
    v_event_digest, v_metadata
  );

  return v_event_digest;
end;
$_$;


ALTER FUNCTION "private"."acp_append_admin_audit_event"("p_action_id" "text", "p_event_type" "text", "p_capability" "text", "p_scope" "jsonb", "p_input_digest" "text", "p_decision" "text", "p_reason_code" "text", "p_execution_status" "text", "p_result_digest" "text", "p_metadata" "jsonb", "p_actor_evidence" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."acp_assert_actor_evidence"("p_evidence" "jsonb") RETURNS "void"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'pg_catalog', 'private'
    AS $_$
begin
  if jsonb_typeof(p_evidence) <> 'object'
     or coalesce(p_evidence->>'repository', '') = ''
     or coalesce(p_evidence->>'workflow_ref', '') = ''
     or coalesce(p_evidence->>'run_id', '') = ''
     or coalesce(p_evidence->>'sha', '') = ''
     or coalesce(p_evidence->>'ref', '') = ''
     or coalesce(p_evidence->>'actor', '') = '' then
    raise exception 'ACP actor evidence incomplete';
  end if;

  if p_evidence->>'repository' <> 'lundus88/fieldgis-reference'
     or p_evidence->>'workflow_ref' <> 'lundus88/fieldgis-reference/.github/workflows/vl-agent-control-plane-admin.yml@refs/heads/main'
     or p_evidence->>'ref' <> 'refs/heads/main'
     or p_evidence->>'sha' !~ '^[0-9a-f]{40}$'
     or p_evidence->>'run_id' !~ '^[0-9]+$' then
    raise exception 'ACP actor evidence identity not allowed';
  end if;

  if p_evidence::text ~* '(authorization|access_token|refresh_token|service_role_key|supabase_service_role_key|api_key|password|private_key|bearer_token|github_token|actions_id_token_request_token)' then
    raise exception 'ACP actor evidence contains forbidden credential field';
  end if;
end;
$_$;


ALTER FUNCTION "private"."acp_assert_actor_evidence"("p_evidence" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."acp_read_agent_grant_chain_nonprod_impl"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO ''
    AS $$
declare
  v_leaf private.agent_capability_grants%rowtype;
  v_rows jsonb;
  v_count integer;
  v_missing_parent boolean;
  v_cycle boolean;
begin
  if p_grant_id is null
     or coalesce(trim(p_agent_id), '') = ''
     or coalesce(trim(p_project_id), '') = ''
     or p_target_environment not in ('development', 'staging') then
    raise exception 'ACP grant query scope invalid';
  end if;

  select *
    into v_leaf
  from private.agent_capability_grants
  where grant_id = p_grant_id;

  if not found then
    raise exception 'ACP grant not found';
  end if;

  if v_leaf.principal_type <> 'agent'
     or v_leaf.agent_id <> p_agent_id
     or coalesce(v_leaf.scope->>'project_id', '') <> p_project_id
     or coalesce(v_leaf.scope->>'target_environment', '') <> p_target_environment then
    raise exception 'ACP grant query leaf mismatch';
  end if;

  if v_leaf.revoked_at is not null
     or v_leaf.valid_from > statement_timestamp()
     or (v_leaf.valid_until is not null and v_leaf.valid_until <= statement_timestamp()) then
    raise exception 'ACP grant query leaf inactive';
  end if;

  if v_leaf.capabilities && array['production.approve','production.promote']::text[] then
    raise exception 'ACP production capability prohibited';
  end if;

  with recursive chain as (
    select
      g.grant_id,
      g.agent_id,
      g.principal_type,
      g.agent_version,
      g.role_name,
      g.capabilities,
      g.scope,
      g.budget,
      g.delegated_from_grant_id,
      g.valid_from,
      g.valid_until,
      g.revoked_at,
      array[g.grant_id]::uuid[] as path,
      1 as depth,
      false as cycle
    from private.agent_capability_grants g
    where g.grant_id = p_grant_id

    union all

    select
      p.grant_id,
      p.agent_id,
      p.principal_type,
      p.agent_version,
      p.role_name,
      p.capabilities,
      p.scope,
      p.budget,
      p.delegated_from_grant_id,
      p.valid_from,
      p.valid_until,
      p.revoked_at,
      c.path || p.grant_id,
      c.depth + 1,
      p.grant_id = any(c.path)
    from chain c
    join private.agent_capability_grants p
      on p.grant_id = c.delegated_from_grant_id
    where c.depth < 16
      and not c.cycle
  ),
  ordered as (
    select *
    from chain
    order by depth
  )
  select
    jsonb_agg(
      jsonb_build_object(
        'grant_id', grant_id::text,
        'agent_id', agent_id,
        'principal_type', principal_type,
        'agent_version', agent_version,
        'role_name', role_name,
        'capabilities', to_jsonb(capabilities),
        'scope', scope,
        'budget', budget,
        'delegated_from_grant_id',
          case when delegated_from_grant_id is null then null else to_jsonb(delegated_from_grant_id::text) end,
        'valid_from', to_jsonb(valid_from),
        'valid_until', to_jsonb(valid_until),
        'revoked_at', to_jsonb(revoked_at)
      )
      order by depth
    ),
    count(*),
    bool_or(cycle)
  into v_rows, v_count, v_cycle
  from ordered;

  if v_count is null or v_count < 1 or v_count > 16 then
    raise exception 'ACP grant chain invalid';
  end if;

  if coalesce(v_cycle, false) then
    raise exception 'ACP delegation cycle detected';
  end if;

  select
    (last_row.delegated_from_grant_id is not null)
  into v_missing_parent
  from (
    with recursive chain as (
      select
        g.grant_id,
        g.delegated_from_grant_id,
        array[g.grant_id]::uuid[] as path,
        1 as depth,
        false as cycle
      from private.agent_capability_grants g
      where g.grant_id = p_grant_id

      union all

      select
        p.grant_id,
        p.delegated_from_grant_id,
        c.path || p.grant_id,
        c.depth + 1,
        p.grant_id = any(c.path)
      from chain c
      join private.agent_capability_grants p
        on p.grant_id = c.delegated_from_grant_id
      where c.depth < 16
        and not c.cycle
    )
    select delegated_from_grant_id
    from chain
    order by depth desc
    limit 1
  ) as last_row;

  if coalesce(v_missing_parent, false) then
    raise exception 'ACP grant chain incomplete';
  end if;

  return v_rows;
end;
$$;


ALTER FUNCTION "private"."acp_read_agent_grant_chain_nonprod_impl"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "private"."acp_read_agent_grant_chain_nonprod_impl"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") IS 'Privileged read-only ACP grant-chain implementation. Not an exposed Data API RPC.';



CREATE OR REPLACE FUNCTION "private"."activate_approved_notification_production"() RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_act private.notification_production_activations%rowtype;
  v_reg private.capability_adapter_registry%rowtype;
begin
  if current_user not in ('service_role','postgres') then
    raise exception 'internal execution role required';
  end if;

  select * into v_act
  from private.notification_production_activations
  where adapter_key='resend-email-v1' and status='approved'
  order by approved_at desc
  limit 1
  for update;

  if not found then
    raise exception 'approved production activation not found';
  end if;

  select * into v_reg
  from private.capability_adapter_registry
  where adapter_key='resend-email-v1'
  for update;

  if not found then
    raise exception 'resend adapter not found';
  end if;

  if coalesce(v_reg.configuration->>'sandbox_e2e_verified_at','')='' or
     coalesce(v_reg.configuration->>'sandbox_reconciliation_verified_at','')='' then
    raise exception 'sandbox evidence incomplete';
  end if;

  if v_reg.status='active' and
     coalesce((v_reg.capabilities->>'production_send_allowed')::boolean,false) and
     coalesce((v_reg.configuration->>'production_send_allowed')::boolean,false) then
    return jsonb_build_object('ok',true,'idempotent',true,'adapter_key',v_reg.adapter_key,'status',v_reg.status);
  end if;

  update private.capability_adapter_registry
  set status='active',
      capabilities=jsonb_set(capabilities,'{production_send_allowed}','true'::jsonb,true),
      configuration=jsonb_set(
        jsonb_set(configuration,'{production_send_allowed}','true'::jsonb,true),
        '{production_activation_approved_at}',to_jsonb(v_act.approved_at),true
      ) || jsonb_build_object('production_activation_approved_by',v_act.approved_by),
      updated_at=now()
  where adapter_key='resend-email-v1';

  update private.notification_production_activations
  set evidence=coalesce(evidence,'{}'::jsonb) || jsonb_build_object('activated_at',now(),'activated_by','internal_role_after_human_approval')
  where id=v_act.id;

  return jsonb_build_object('ok',true,'idempotent',false,'adapter_key','resend-email-v1','status','active','activation_id',v_act.id);
end
$$;


ALTER FUNCTION "private"."activate_approved_notification_production"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."activate_notification_adapter_if_approved"() RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare v_act private.notification_production_activations%rowtype; v_reg private.capability_adapter_registry%rowtype;
begin
  if current_user not in ('service_role','postgres') then raise exception 'service role required'; end if;
  select * into v_act from private.notification_production_activations where adapter_key='resend-email-v1';
  if not found or v_act.status<>'approved' then raise exception 'explicit human production activation approval required'; end if;
  select * into v_reg from private.capability_adapter_registry where adapter_key='resend-email-v1' for update;
  if coalesce(v_reg.configuration->>'sandbox_e2e_verified_at','')='' or coalesce(v_reg.configuration->>'sandbox_reconciliation_verified_at','')='' then raise exception 'sandbox evidence incomplete'; end if;
  update private.capability_adapter_registry
  set status='active',
      capabilities=jsonb_set(capabilities,'{production_send_allowed}','true'::jsonb,true),
      configuration=jsonb_set(jsonb_set(configuration,'{production_send_allowed}','true'::jsonb,true),'{production_activation_approved_at}',to_jsonb(v_act.approved_at),true),
      updated_at=now()
  where adapter_key='resend-email-v1';
  return private.notification_production_readiness();
end$$;


ALTER FUNCTION "private"."activate_notification_adapter_if_approved"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'pg_temp'
    AS $$
declare
  v_order private.payment_sandbox_orders%rowtype;
  v_existing private.payment_webhook_events%rowtype;
  v_applied boolean := false;
  v_now timestamptz := now();
  v_reason text := 'no_state_change';
begin
  if coalesce(trim(p_event_key),'') = '' or coalesce(trim(p_provider_bill_id),'') = '' then
    raise exception 'invalid webhook identity';
  end if;
  if p_normalized_status not in ('paid','pending','cancelled','refunded') then
    raise exception 'invalid normalized status';
  end if;

  select * into v_existing from private.payment_webhook_events where event_key = p_event_key;
  if found then
    return jsonb_build_object('ok',true,'duplicate',true,'applied',false,'status',v_existing.normalized_status,'reason','duplicate_event');
  end if;

  select * into v_order from private.payment_sandbox_orders
   where provider_bill_id = p_provider_bill_id
   for update;
  if not found then raise exception 'unknown sandbox bill'; end if;
  if v_order.environment <> 'sandbox' or v_order.adapter_key <> 'billplz-payment-v1' then
    raise exception 'sandbox adapter invariant failed';
  end if;
  if p_amount_minor is distinct from v_order.amount_minor then raise exception 'amount mismatch'; end if;
  if v_order.currency <> 'MYR' then raise exception 'currency mismatch'; end if;

  if p_normalized_status = 'paid' then
    if v_order.status = 'pending' and v_order.fulfillment_state = 'unfulfilled' then
      update private.payment_sandbox_orders
         set status='paid', paid_at=coalesce(paid_at,v_now), updated_at=v_now,
             metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
               'payment_confirmed_by','billplz_signed_webhook',
               'fulfillment_separated',true
             )
       where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
      v_applied := found;
      v_reason := case when v_applied then 'pending_to_paid' else 'race_blocked' end;
    elsif v_order.status in ('cancelled','refunded') then
      v_reason := 'terminal_order_not_resurrected';
    else
      v_reason := 'paid_state_unchanged';
    end if;
  elsif p_normalized_status = 'cancelled' then
    update private.payment_sandbox_orders
       set status='cancelled',updated_at=v_now
     where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'pending_to_cancelled' else 'cancellation_not_applicable' end;
  elsif p_normalized_status = 'refunded' then
    update private.payment_sandbox_orders
       set status='refunded',fulfillment_state='reversed',updated_at=v_now,
           metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object('refund_confirmed_by','billplz_signed_webhook')
     where id=v_order.id and status='paid' and fulfillment_state='fulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'paid_to_refunded_reversed' else 'refund_not_applicable' end;
  end if;

  begin
    insert into private.payment_webhook_events(
      adapter_key,event_key,provider_bill_id,payload_sha256,signature_valid,
      normalized_status,amount_minor,applied,duplicate,processed_at,metadata
    ) values (
      'billplz-payment-v1',p_event_key,p_provider_bill_id,p_payload_sha256,true,
      p_normalized_status,p_amount_minor,v_applied,false,v_now,
      jsonb_build_object('environment','sandbox','authoritative_source','server_callback','fulfillment_mutated',p_normalized_status='refunded' and v_applied,'reason',v_reason)
    );
  exception when unique_violation then
    return jsonb_build_object('ok',true,'duplicate',true,'applied',false,'status',p_normalized_status,'reason','duplicate_event');
  end;

  return jsonb_build_object('ok',true,'duplicate',false,'applied',v_applied,'status',p_normalized_status,'reason',v_reason,'fulfillment_mutated',p_normalized_status='refunded' and v_applied);
end;
$$;


ALTER FUNCTION "private"."apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."apply_resend_sandbox_webhook"("p_event_key" "text", "p_provider_message_id" "text", "p_event_type" "text", "p_status" "text", "p_payload_sha256" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'pg_temp'
    AS $$
declare
  v_existing private.notification_events%rowtype;
  v_current text;
  v_next text;
  v_rows int := 0;
  v_matched boolean := false;
  v_applied boolean := false;
begin
  if coalesce(trim(p_event_key),'')='' then raise exception 'event_key required'; end if;
  select * into v_existing from private.notification_events where event_key=p_event_key;
  if found then return jsonb_build_object('duplicate',true,'applied',false,'event_type',p_event_type); end if;

  if coalesce(p_provider_message_id,'')<>'' and p_status is not null then
    select status into v_current
      from private.notification_outbox
      where provider_message_id=p_provider_message_id
        and adapter_key='resend-email-v1'
        and environment='sandbox'
      for update;
    if found then
      v_matched := true;
      v_next := case
        when v_current in ('bounced','failed') then v_current
        when p_status in ('bounced','failed') then p_status
        when v_current='delivered' then 'delivered'
        when p_status='delivered' then 'delivered'
        when v_current='sent' then 'sent'
        when p_status='sent' then 'sent'
        else coalesce(p_status,v_current)
      end;
      if v_next is distinct from v_current then
        update private.notification_outbox set status=v_next,updated_at=now()
          where provider_message_id=p_provider_message_id
            and adapter_key='resend-email-v1' and environment='sandbox';
        get diagnostics v_rows=row_count;
        v_applied := v_rows>0;
      end if;
    end if;
  end if;

  begin
    insert into private.notification_events(adapter_key,provider_message_id,event_key,event_type,signature_valid,payload_sha256,duplicate,applied,processed_at,metadata)
    values('resend-email-v1',nullif(p_provider_message_id,''),p_event_key,coalesce(nullif(p_event_type,''),'unknown'),true,p_payload_sha256,false,v_applied,now(),jsonb_build_object('environment','sandbox','pii_stored',false,'matched_outbox',v_matched,'previous_status',v_current,'resulting_status',coalesce(v_next,v_current)));
  exception when unique_violation then
    return jsonb_build_object('duplicate',true,'applied',false,'event_type',p_event_type);
  end;
  return jsonb_build_object('duplicate',false,'applied',v_applied,'event_type',p_event_type,'status',coalesce(v_next,v_current));
end $$;


ALTER FUNCTION "private"."apply_resend_sandbox_webhook"("p_event_key" "text", "p_provider_message_id" "text", "p_event_type" "text", "p_status" "text", "p_payload_sha256" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."approve_and_launch_app_spec"("p_app_spec_id" "uuid", "p_approver_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_spec public.app_specs%rowtype;
  v_builder_key text;
  v_builder_status text;
  v_workflow_id uuid;
  v_factory_run_id uuid;
  v_role text;
  v_run_type text := 'build';
  v_workflow_type text := 'factory_build';
  v_base_run_id uuid;
  v_upgrade_seed jsonb;
begin
  select * into v_spec from public.app_specs where id=p_app_spec_id for update;
  if not found then raise exception 'App Spec not found'; end if;
  select pm.role into v_role from public.project_members pm where pm.project_id=v_spec.project_id and pm.user_id=p_approver_id;
  if v_role not in ('owner','admin') then raise exception 'Only project owner/admin may approve and launch App Spec'; end if;
  if v_spec.status not in ('draft','approved') then raise exception 'App Spec status % cannot be launched',v_spec.status; end if;

  v_builder_key:=v_spec.spec #>> '{selected_builder,builder_key}';
  if v_builder_key is null or btrim(v_builder_key)='' then raise exception 'App Spec has no selected builder'; end if;
  select br.status into v_builder_status from public.builder_registry br where br.builder_key=v_builder_key;
  if v_builder_status is distinct from 'active' then raise exception 'Selected builder % is not active',v_builder_key; end if;

  if v_spec.parent_app_spec_id is not null then
    v_run_type:='upgrade'; v_workflow_type:='factory_upgrade';
    select fr.id into v_base_run_id from public.factory_runs fr
    where fr.app_spec_id=v_spec.parent_app_spec_id and fr.state in ('awaiting_approval','certified')
      and coalesce(fr.result->>'runner_status','')='PASS'
    order by fr.created_at desc limit 1;
    if v_base_run_id is null then raise exception 'upgrade requires a successful base factory run for parent App Spec'; end if;
  end if;

  if v_spec.status<>'approved' then update public.app_specs set status='approved',approved_by=p_approver_id,approved_at=now() where id=p_app_spec_id; end if;

  insert into public.workflows(project_id,app_spec_id,workflow_type,state,input,output,created_by)
  values(v_spec.project_id,p_app_spec_id,v_workflow_type,'queued',jsonb_build_object('builder_key',v_builder_key,'source','approved_app_spec','run_type',v_run_type,'base_factory_run_id',v_base_run_id),'{}'::jsonb,p_approver_id)
  returning id into v_workflow_id;

  insert into public.factory_runs(project_id,app_spec_id,workflow_id,requested_by,run_type,state,target_environment,production_locked,input,plan,result,target_platforms,base_factory_run_id)
  values(v_spec.project_id,p_app_spec_id,v_workflow_id,p_approver_id,v_run_type,'queued','staging',true,
    jsonb_build_object('builder_key',v_builder_key,'app_spec_id',p_app_spec_id,'base_factory_run_id',v_base_run_id,'change_request',v_spec.change_request),
    jsonb_build_object('selected_builder',v_builder_key,'target_platforms',v_spec.target_platforms,'approval_required_for_production',true,'run_type',v_run_type,'base_factory_run_id',v_base_run_id),
    '{}'::jsonb,v_spec.target_platforms,v_base_run_id)
  returning id into v_factory_run_id;

  if v_run_type='upgrade' then
    v_upgrade_seed:=private.seed_upgrade_source_from_base(v_factory_run_id,v_base_run_id,v_spec.change_request);
  end if;

  insert into private.app_launch_audit(app_spec_id,project_id,approver_id,builder_key,workflow_id,factory_run_id,decision,details)
  values(p_app_spec_id,v_spec.project_id,p_approver_id,v_builder_key,v_workflow_id,v_factory_run_id,'launched',jsonb_build_object('environment','staging','production_locked',true,'run_type',v_run_type,'base_factory_run_id',v_base_run_id,'upgrade_seed',v_upgrade_seed));

  return jsonb_build_object('decision','launched','app_spec_id',p_app_spec_id,'builder_key',v_builder_key,'workflow_id',v_workflow_id,'factory_run_id',v_factory_run_id,'run_type',v_run_type,'base_factory_run_id',v_base_run_id,'target_environment','staging','production_locked',true,'upgrade_seed',v_upgrade_seed);
end;
$$;


ALTER FUNCTION "private"."approve_and_launch_app_spec"("p_app_spec_id" "uuid", "p_approver_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."approve_notification_production_activation"("p_rationale" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  v_reg private.capability_adapter_registry%rowtype;
  v_act private.notification_production_activations%rowtype;
  v_is_owner boolean:=false;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for notification production activation approval'; end if;

  select exists(select 1 from public.project_members pm where pm.user_id=v_uid and pm.role in ('owner','admin')) into v_is_owner;
  if not v_is_owner then raise exception 'owner/admin activation approval required'; end if;

  select * into v_reg from private.capability_adapter_registry where adapter_key='resend-email-v1' for update;
  if not found then raise exception 'resend-email-v1 adapter not found'; end if;
  if coalesce(v_reg.configuration->>'sandbox_e2e_verified_at','')='' then raise exception 'sandbox E2E evidence required'; end if;
  if coalesce(v_reg.configuration->>'sandbox_reconciliation_verified_at','')='' then raise exception 'sandbox reconciliation evidence required'; end if;

  select * into v_act from private.notification_production_activations where adapter_key='resend-email-v1' for update;
  if v_act.status='approved' then
    return jsonb_build_object('ok',true,'decision','already_approved','adapter_key','resend-email-v1','approved_by',v_act.approved_by,'approved_at',v_act.approved_at,'idempotent',true,'authenticator_assurance_level',v_aal,'mfa_enforced',true);
  end if;

  update private.notification_production_activations
  set status='approved',approved_at=now(),approved_by=v_uid,
      rationale=coalesce(nullif(p_rationale,''),'Explicit owner/admin approval for controlled production alert activation'),
      evidence=jsonb_build_object(
        'explicit_human_approval',true,
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'sandbox_e2e_verified_at',v_reg.configuration->>'sandbox_e2e_verified_at',
        'sandbox_reconciliation_verified_at',v_reg.configuration->>'sandbox_reconciliation_verified_at',
        'production_runtime_config_must_be_verified_by_dispatcher',true
      )
  where adapter_key='resend-email-v1';

  return jsonb_build_object('ok',true,'decision','notification_production_activation_approved','adapter_key','resend-email-v1','approved_by',v_uid,'approved_at',now(),'idempotent',false,'authenticator_assurance_level',v_aal,'mfa_enforced',true);
end
$$;


ALTER FUNCTION "private"."approve_notification_production_activation"("p_rationale" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."approve_production_release"("p_deployment_id" "uuid", "p_rationale" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  v_dep public.deployments%rowtype;
  v_run public.factory_runs%rowtype;
  v_required jsonb;
  v_missing int;
  v_approval public.approvals%rowtype;
  v_eligible_approvers int:=0;
  v_other_approvers int:=0;
  v_solo_exception boolean:=false;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for production approval'; end if;

  select * into v_dep from public.deployments where id=p_deployment_id for update;
  if not found then raise exception 'deployment not found'; end if;
  if not private.has_project_role(v_dep.project_id,array['owner','admin']) then raise exception 'owner/admin production approval required'; end if;

  if v_dep.status in ('approved','deploying','deployed') and v_dep.approved_by is not null then
    select * into v_approval from public.approvals where factory_run_id=v_dep.factory_run_id and approval_type='production_release' limit 1;
    return jsonb_build_object('decision','production_release_already_approved','deployment_id',v_dep.id,'factory_run_id',v_dep.factory_run_id,'approval_id',v_approval.id,'approved_by',v_dep.approved_by,'artifact_sha256',v_dep.artifact_sha256,'idempotent',true);
  end if;

  if v_dep.status<>'certified' then raise exception 'deployment must be technically certified before approval'; end if;
  select * into v_run from public.factory_runs where id=v_dep.factory_run_id and project_id=v_dep.project_id for update;
  if not found then raise exception 'factory run not found'; end if;
  if v_dep.workflow_id is distinct from v_run.workflow_id then raise exception 'deployment workflow mismatch'; end if;

  v_required:=private.get_deployment_required_release_gates(v_dep.id);
  select count(*) into v_missing from jsonb_array_elements(v_required) g where not exists(select 1 from public.release_gates rg where rg.factory_run_id=v_run.id and rg.gate_key=g->>'key' and rg.status='pass');
  if v_missing>0 then raise exception 'technical release gates not all PASS'; end if;

  select * into v_approval from public.approvals where factory_run_id=v_run.id and approval_type='production_release' for update;
  if not found then raise exception 'production approval record required'; end if;
  if v_approval.status='approved' then
    return jsonb_build_object('decision','production_release_already_approved','deployment_id',v_dep.id,'factory_run_id',v_run.id,'approval_id',v_approval.id,'approved_by',v_approval.decided_by,'artifact_sha256',v_dep.artifact_sha256,'idempotent',true);
  end if;
  if v_approval.status<>'pending' then raise exception 'production approval is not pending'; end if;

  select count(*) into v_eligible_approvers from public.project_members pm where pm.project_id=v_dep.project_id and pm.role in ('owner','admin');
  select count(*) into v_other_approvers from public.project_members pm where pm.project_id=v_dep.project_id and pm.role in ('owner','admin') and pm.user_id<>v_uid;

  if v_approval.requested_by=v_uid then
    if v_other_approvers>0 then
      raise exception 'production approval blocked by separation-of-duties: requester cannot approve when another owner/admin is available';
    end if;
    v_solo_exception:=true;
  end if;

  update public.approvals
  set status='approved',
      decided_by=v_uid,
      decided_at=now(),
      rationale=coalesce(nullif(p_rationale,''),rationale,case when v_solo_exception then 'Explicit solo-operator production approval; no second owner/admin available' else 'Explicit owner/admin production approval' end)
  where id=v_approval.id;

  update public.release_gates
  set status='pass',score=1,
      evidence=jsonb_build_object(
        'approval_id',v_approval.id,
        'approved_by',v_uid,
        'approved_at',now(),
        'explicit_human_approval',true,
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end,
        'eligible_approver_count',v_eligible_approvers,
        'requester_is_approver',v_approval.requested_by=v_uid
      ),
      checked_at=now(),checked_by=v_uid
  where factory_run_id=v_run.id and gate_key='human_production_approval';

  update public.release_gates
  set status='pass',score=1,
      evidence=jsonb_build_object(
        'release_unlock','approved',
        'approved_by',v_uid,
        'approved_at',now(),
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'factory_run_remains_immutable',true,
        'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end
      ),
      checked_at=now(),checked_by=v_uid
  where factory_run_id=v_run.id and gate_key='production_lock';

  update public.deployments
  set status='approved',approved_by=v_uid,
      certificate=certificate||jsonb_build_object(
        'human_approval','PASS',
        'approved_by',v_uid,
        'approved_at',now(),
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'production_release_authorized',true,
        'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end,
        'eligible_approver_count',v_eligible_approvers,
        'requester_is_approver',v_approval.requested_by=v_uid
      )
  where id=v_dep.id;

  return jsonb_build_object(
    'decision','production_release_approved',
    'deployment_id',v_dep.id,
    'factory_run_id',v_run.id,
    'approval_id',v_approval.id,
    'approved_by',v_uid,
    'artifact_sha256',v_dep.artifact_sha256,
    'next_state','approved',
    'authenticator_assurance_level',v_aal,
    'mfa_enforced',true,
    'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end,
    'eligible_approver_count',v_eligible_approvers,
    'idempotent',false
  );
end
$$;


ALTER FUNCTION "private"."approve_production_release"("p_deployment_id" "uuid", "p_rationale" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."auto_prepare_release_candidate"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  if new.state='validating'
     and new.target_environment='staging'
     and new.production_locked=true
     and coalesce(new.result->>'runner_status','')='PASS'
     and not exists (
       select 1 from public.deployments d
       where d.factory_run_id=new.id
         and d.project_id=new.project_id
     ) then
    begin
      perform private.ensure_release_candidate(new.id,new.requested_by);
    exception when others then
      insert into private.factory_execution_events(
        factory_run_id,project_id,event_type,from_state,to_state,payload
      ) values(
        new.id,new.project_id,'release_candidate_prepare_blocked',old.state,new.state,
        jsonb_build_object('error',sqlerrm,'phase','validating_after_runner_pass')
      );
    end;
  end if;
  return new;
end
$$;


ALTER FUNCTION "private"."auto_prepare_release_candidate"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."begin_factory_validation"("p_factory_run_id" "uuid", "p_build_result" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare r public.factory_runs%rowtype;
begin
  select * into r from public.factory_runs where id=p_factory_run_id for update;
  if not found then raise exception 'Factory run not found'; end if;
  if r.state <> 'building' then raise exception 'Factory run must be building'; end if;
  update public.factory_runs set state='validating', result=coalesce(result,'{}'::jsonb)||jsonb_build_object('build',p_build_result) where id=r.id;
  insert into private.factory_execution_events(factory_run_id,project_id,event_type,from_state,to_state,payload)
  values(r.id,r.project_id,'validation_started','building','validating',p_build_result);
  return jsonb_build_object('decision','validating','state','validating');
end;
$$;


ALTER FUNCTION "private"."begin_factory_validation"("p_factory_run_id" "uuid", "p_build_result" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."billplz_production_readiness"() RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
select jsonb_build_object(
  'adapter_key',r.adapter_key,
  'adapter_status',r.status,
  'live_charge_allowed',coalesce((r.capabilities->>'live_charge_allowed')::boolean,false) and coalesce((r.configuration->>'live_charge_allowed')::boolean,false),
  'sandbox_e2e_verified_at',r.configuration->>'sandbox_e2e_verified_at',
  'production_credentials_configured',coalesce((r.configuration->>'production_credentials_configured')::boolean,false)
)
from private.capability_adapter_registry r where r.adapter_key='billplz-payment-v1';
$$;


ALTER FUNCTION "private"."billplz_production_readiness"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."block_agent_audit_mutation"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'pg_catalog', 'private'
    AS $$
begin
  raise exception 'agent_control_audit_events is append-only';
end;
$$;


ALTER FUNCTION "private"."block_agent_audit_mutation"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."build_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "private"."build_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."claim_operational_alert_job"("p_runner_identity" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare v private.operational_incidents%rowtype; tok uuid:=gen_random_uuid(); ready jsonb;
begin
  ready:=private.notification_production_readiness();
  if coalesce((ready->>'production_send_allowed')::boolean,false) is not true or coalesce(ready->>'adapter_status','')<>'active' then
    return jsonb_build_object('status','blocked','reason','notification production adapter is not active/allowed','readiness',ready);
  end if;
  select * into v from private.operational_incidents
   where status<>'resolved' and severity in ('sev1','sev2')
     and alert_state in ('pending','failed') and alert_attempts<3
   order by case severity when 'sev1' then 1 else 2 end, started_at
   for update skip locked limit 1;
  if not found then return jsonb_build_object('status','idle'); end if;
  update private.operational_incidents set alert_state='leased',alert_attempts=alert_attempts+1,alert_lease_token=tok,alert_leased_at=now(),alert_error_text=null where id=v.id;
  return jsonb_build_object('status','leased','incident_id',v.id,'incident_key',v.incident_key,'severity',v.severity,'summary',v.summary,'started_at',v.started_at,'lease_token',tok,'attempt',v.alert_attempts+1,'runner_identity',p_runner_identity);
end $$;


ALTER FUNCTION "private"."claim_operational_alert_job"("p_runner_identity" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."compile_app_request"("p_prompt" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
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
    and v_prompt !~ '(no (device )?gps|without (device )?gps|(device )?gps (is )?not required|no (device )?gnss|without (device )?gnss|(device )?gnss (is )?not required|no device location|without device location|device location (is )?not required|no current location|without current location|current location (is )?not required|no live location|without live location|location tracking (is )?not required|do not track (my )?(position|location))';
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
    'compiler_version','1.9',
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
$$;


ALTER FUNCTION "private"."compile_app_request"("p_prompt" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."complete_factory_validation"("p_factory_run_id" "uuid", "p_pass" boolean, "p_qa" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare r public.factory_runs%rowtype;
begin
  select * into r from public.factory_runs where id=p_factory_run_id for update;
  if not found then raise exception 'Factory run not found'; end if;
  if r.state <> 'validating' then raise exception 'Factory run must be validating'; end if;

  if p_pass then
    update public.factory_runs
    set state='awaiting_approval', result=coalesce(result,'{}'::jsonb)||jsonb_build_object('qa',p_qa,'technical_certification','PASS')
    where id=r.id;
    update public.workflows set state='waiting_approval', output=coalesce(output,'{}'::jsonb)||jsonb_build_object('qa',p_qa) where id=r.workflow_id;
    insert into private.factory_execution_events(factory_run_id,project_id,event_type,from_state,to_state,payload)
    values(r.id,r.project_id,'validation_passed','validating','awaiting_approval',p_qa);
    return jsonb_build_object('decision','awaiting_approval','state','awaiting_approval','production_locked',r.production_locked);
  else
    update public.factory_runs set state='failed', error_text='Factory validation failed', finished_at=now(), result=coalesce(result,'{}'::jsonb)||jsonb_build_object('qa',p_qa,'technical_certification','FAIL') where id=r.id;
    update public.workflows set state='failed', finished_at=now(), output=coalesce(output,'{}'::jsonb)||jsonb_build_object('qa',p_qa) where id=r.workflow_id;
    insert into private.factory_execution_events(factory_run_id,project_id,event_type,from_state,to_state,payload)
    values(r.id,r.project_id,'validation_failed','validating','failed',p_qa);
    return jsonb_build_object('decision','failed','state','failed');
  end if;
end;
$$;


ALTER FUNCTION "private"."complete_factory_validation"("p_factory_run_id" "uuid", "p_pass" boolean, "p_qa" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."complete_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text" DEFAULT NULL::"text", "p_error_text" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare n int;
begin
  update private.operational_incidents set
    alert_state=case when p_success then 'sent' else 'failed' end,
    alert_sent_at=case when p_success then now() else alert_sent_at end,
    alert_error_text=case when p_success then null else left(coalesce(p_error_text,'unknown error'),2000) end,
    alert_lease_token=null,alert_leased_at=null,
    evidence=evidence || jsonb_build_object('alert_provider_message_id',p_provider_message_id,'alert_completed_at',now())
  where id=p_incident_id and alert_state='leased' and alert_lease_token=p_lease_token;
  get diagnostics n=row_count;
  if n<>1 then raise exception 'invalid or stale alert lease'; end if;
  return jsonb_build_object('ok',true,'incident_id',p_incident_id,'state',case when p_success then 'sent' else 'failed' end);
end $$;


ALTER FUNCTION "private"."complete_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text", "p_error_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."create_app_spec_revision"("p_base_app_spec_id" "uuid", "p_change_request" "text", "p_actor" "uuid") RETURNS "uuid"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_base public.app_specs%rowtype;
  v_new_id uuid;
  v_next_version integer;
  v_spec jsonb;
begin
  if p_actor is null then raise exception 'revision actor required'; end if;
  if nullif(btrim(p_change_request),'') is null then raise exception 'change request required'; end if;

  select * into v_base from public.app_specs where id=p_base_app_spec_id;
  if not found then raise exception 'base app spec not found'; end if;
  if not exists (
    select 1 from public.project_members pm
    where pm.project_id=v_base.project_id and pm.user_id=p_actor and pm.role in ('owner','admin','builder')
  ) then raise exception 'actor is not authorized project member'; end if;

  select coalesce(max(version),0)+1 into v_next_version
  from public.app_specs where project_id=v_base.project_id;

  v_spec := jsonb_set(
    coalesce(v_base.spec,'{}'::jsonb),
    '{revision}',
    jsonb_build_object(
      'kind','upgrade',
      'base_app_spec_id',v_base.id,
      'base_version',v_base.version,
      'change_request',p_change_request,
      'created_at',now()
    ),
    true
  );

  insert into public.app_specs(
    project_id,version,title,objective,spec,status,created_by,software_kind,target_platforms,
    parent_app_spec_id,change_request
  ) values (
    v_base.project_id,v_next_version,v_base.title,
    v_base.objective || E'\n\nRequested revision: ' || p_change_request,
    v_spec,'draft',p_actor,v_base.software_kind,v_base.target_platforms,
    v_base.id,p_change_request
  ) returning id into v_new_id;

  return v_new_id;
end;
$$;


ALTER FUNCTION "private"."create_app_spec_revision"("p_base_app_spec_id" "uuid", "p_change_request" "text", "p_actor" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_approved_app_spec_for_factory_run"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO ''
    AS $$
declare
  v_status text;
begin
  if new.run_type = 'build' and new.app_spec_id is not null then
    select a.status into v_status
    from public.app_specs a
    where a.id = new.app_spec_id;

    if v_status is distinct from 'approved' then
      raise exception 'VRS build requires an approved App Spec';
    end if;
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."enforce_approved_app_spec_for_factory_run"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_assisted_build_execution_gate"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public', 'private', 'auth', 'pg_temp'
    AS $$
declare
  v_spec public.app_specs%rowtype;
  v_policy private.assisted_build_cost_policy%rowtype;
  v_account public.customer_accounts%rowtype;
  v_limits jsonb;
  v_mode text;
  v_allowance integer;
  v_estimate integer;
  v_used integer;
  v_complexity text;
  v_builder_key text;
  v_confirmed_at text;
begin
  select * into v_spec from public.app_specs where id=new.app_spec_id;
  if not found or coalesce(v_spec.spec->>'source','') <> 'assisted_build' then
    return new;
  end if;

  if new.target_environment <> 'staging' or new.production_locked is distinct from true then
    raise exception 'assisted build execution must be staging-only and production-locked' using errcode='42501';
  end if;

  if coalesce((v_spec.spec #>> '{provenance,user_confirmed}')::boolean,false) is distinct from true then
    raise exception 'assisted build customer confirmation required' using errcode='P0001';
  end if;
  v_confirmed_at := nullif(v_spec.spec #>> '{provenance,confirmed_at}','');
  if v_confirmed_at is null then
    raise exception 'assisted build confirmation timestamp required' using errcode='P0001';
  end if;

  v_builder_key := nullif(v_spec.spec #>> '{selected_builder,builder_key}','');
  if v_builder_key is null then
    raise exception 'assisted build selected builder contract required' using errcode='P0001';
  end if;

  v_complexity := nullif(v_spec.spec #>> '{complexity,classification}','');
  select * into v_policy
  from private.assisted_build_cost_policy
  where complexity_class=v_complexity and enabled=true;
  if not found then
    raise exception 'assisted build authoritative cost policy unavailable' using errcode='P0001';
  end if;

  begin
    v_estimate := (v_spec.spec #>> '{commercial,factory_credit_estimate}')::integer;
  exception when others then
    raise exception 'assisted build Factory Credit estimate required' using errcode='P0001';
  end;
  if v_estimate is distinct from v_policy.factory_credit_estimate then
    raise exception 'assisted build Factory Credit estimate does not match authoritative policy' using errcode='P0001';
  end if;

  select * into v_account
  from public.customer_accounts
  where owner_user_id=new.requested_by
  for update;
  if not found or v_account.status <> 'active' or v_account.onboarding_state <> 'ready' or v_account.terms_accepted_at is null then
    raise exception 'launch-ready customer account required for assisted build execution' using errcode='42501';
  end if;

  select limits into v_limits
  from public.plan_catalog
  where plan_key=v_account.plan_key and is_public=true;
  if v_limits is null then
    raise exception 'assisted build plan policy unavailable' using errcode='42501';
  end if;

  v_mode := coalesce(v_limits->>'assisted_build_execution_mode','');
  begin
    v_allowance := coalesce((v_limits->>'assisted_build_factory_credits_per_day')::integer,0);
  exception when others then
    v_allowance := 0;
  end;

  if v_mode <> 'pilot_entitlement' or v_allowance <= 0 then
    raise exception 'assisted build execution authorization unavailable; verified credit/payment required' using errcode='42501';
  end if;

  select coalesce(sum((fr.input #>> '{assisted_build_execution_authorization,factory_credit_estimate}')::integer),0)
  into v_used
  from public.factory_runs fr
  where fr.requested_by=new.requested_by
    and fr.created_at >= (date_trunc('day',now() at time zone 'UTC') at time zone 'UTC')
    and fr.input ? 'assisted_build_execution_authorization';

  if v_used + v_estimate > v_allowance then
    raise exception 'assisted build daily Factory Credit allowance exceeded' using errcode='P0001';
  end if;

  new.input := coalesce(new.input,'{}'::jsonb) || jsonb_build_object(
    'assisted_build_execution_authorization',jsonb_build_object(
      'source','pilot_entitlement',
      'plan_key',v_account.plan_key,
      'factory_credit_estimate',v_estimate,
      'daily_factory_credit_allowance',v_allowance,
      'daily_factory_credit_used_before',v_used,
      'pricing_source','private.assisted_build_cost_policy',
      'commercial_payment_bypassed',false,
      'production_approval_bypassed',false,
      'production_promotion_bypassed',false
    )
  );

  insert into private.usage_counters(customer_account_id,metric_key,window_start,window_end,used_count,limit_count)
  values(
    v_account.id,
    'assisted_build_factory_credits',
    date_trunc('day',now() at time zone 'UTC') at time zone 'UTC',
    (date_trunc('day',now() at time zone 'UTC')+interval '1 day') at time zone 'UTC',
    v_used+v_estimate,
    v_allowance
  )
  on conflict(customer_account_id,metric_key,window_start,window_end) do update
  set used_count=excluded.used_count,limit_count=excluded.limit_count,updated_at=now();

  return new;
end;
$$;


ALTER FUNCTION "private"."enforce_assisted_build_execution_gate"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_deployment_snapshot_immutability"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $_$
declare
  v_calc_hash text;
begin
  -- Materialize immutable snapshot columns from the release certificate when
  -- they have not yet been populated. This keeps certificate JSON and typed
  -- columns in one deterministic contract.
  if new.required_gates_snapshot is null and jsonb_typeof(new.certificate->'required_gates')='array' then
    new.required_gates_snapshot := new.certificate->'required_gates';
  end if;
  if new.builder_key_snapshot is null then
    new.builder_key_snapshot := nullif(new.certificate->>'builder_key','');
  end if;
  if new.builder_version_snapshot is null and coalesce(new.certificate->>'builder_version','') ~ '^[0-9]+$' then
    new.builder_version_snapshot := (new.certificate->>'builder_version')::integer;
  end if;
  if new.gate_policy_version_snapshot is null and coalesce(new.certificate->>'gate_policy_version','') ~ '^[0-9]+$' then
    new.gate_policy_version_snapshot := (new.certificate->>'gate_policy_version')::integer;
  end if;
  if new.gate_policy_sha256 is null then
    new.gate_policy_sha256 := nullif(new.certificate->>'gate_policy_sha256','');
  end if;
  if new.builder_profile_sha256_snapshot is null then
    new.builder_profile_sha256_snapshot := nullif(new.certificate->>'builder_profile_sha256','');
  end if;
  if new.app_spec_sha256 is null then
    new.app_spec_sha256 := nullif(new.certificate->>'app_spec_sha256','');
  end if;
  if new.source_commit_sha is null then
    new.source_commit_sha := nullif(new.certificate->>'source_commit_sha','');
  end if;

  if new.required_gates_snapshot is not null then
    v_calc_hash := encode(extensions.digest(convert_to(new.required_gates_snapshot::text,'UTF8'),'sha256'),'hex');
    if new.gate_policy_sha256 is null then
      new.gate_policy_sha256 := v_calc_hash;
    elsif lower(new.gate_policy_sha256) <> lower(v_calc_hash) then
      raise exception 'deployment gate policy hash does not match required gate snapshot';
    end if;
  end if;

  if tg_op='UPDATE' and old.gate_policy_sha256 is not null then
    if new.factory_run_id is distinct from old.factory_run_id
       or new.required_gates_snapshot is distinct from old.required_gates_snapshot
       or new.builder_key_snapshot is distinct from old.builder_key_snapshot
       or new.builder_version_snapshot is distinct from old.builder_version_snapshot
       or new.gate_policy_version_snapshot is distinct from old.gate_policy_version_snapshot
       or new.gate_policy_sha256 is distinct from old.gate_policy_sha256
       or new.builder_profile_sha256_snapshot is distinct from old.builder_profile_sha256_snapshot
       or new.app_spec_sha256 is distinct from old.app_spec_sha256
       or new.source_commit_sha is distinct from old.source_commit_sha then
      raise exception 'deployment certification snapshot is immutable';
    end if;
  end if;

  if new.status in ('certified','approved','deploying','deployed') then
    if new.factory_run_id is null or new.required_gates_snapshot is null
       or new.builder_key_snapshot is null or new.builder_version_snapshot is null
       or new.gate_policy_version_snapshot is null or new.gate_policy_sha256 is null then
      raise exception 'certified deployment requires immutable certification snapshot';
    end if;
  end if;
  return new;
end
$_$;


ALTER FUNCTION "private"."enforce_deployment_snapshot_immutability"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_factory_artifact_immutability"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $_$
declare
  v_referenced boolean := false;
  v_run_state text;
  v_old_base jsonb;
  v_new_base jsonb;
  v_old_id text;
  v_new_id text;
  v_old_digest text;
  v_new_digest text;
  v_old_exp text;
  v_new_exp text;
  v_old_reconciled_at text;
  v_new_reconciled_at text;
  v_old_source text;
  v_new_source text;
begin
  if tg_op='INSERT' then
    if new.sha256 is not null and new.sha256 !~ '^[0-9a-fA-F]{64}$' then raise exception 'factory artifact sha256 must be a valid SHA-256 hex digest'; end if;
    return new;
  end if;

  select exists(
    select 1 from public.deployments d
    where d.factory_run_id=old.factory_run_id
      and lower(coalesce(d.artifact_sha256,''))=lower(coalesce(old.sha256,''))
      and d.status in ('planned','certified','approved','deploying','deployed')
  ) into v_referenced;
  select state into v_run_state from public.factory_runs where id=old.factory_run_id;

  if tg_op='DELETE' then
    if v_referenced then raise exception 'immutable factory artifact: artifact is referenced by a release deployment'; end if;
    if v_run_state not in ('queued','building','validating','failed') then raise exception 'immutable factory artifact: deletion not allowed after factory run leaves mutable states'; end if;
    return old;
  end if;

  if new.factory_run_id is distinct from old.factory_run_id
     or new.project_id is distinct from old.project_id
     or new.artifact_type is distinct from old.artifact_type
     or new.name is distinct from old.name
     or new.storage_path is distinct from old.storage_path
     or new.sha256 is distinct from old.sha256
     or new.created_at is distinct from old.created_at then
    if v_referenced then raise exception 'immutable factory artifact: release-bound identity/content fields cannot be changed'; end if;
    if v_run_state not in ('building','validating') then raise exception 'immutable factory artifact: identity/content fields may only change during building/validating'; end if;
  end if;

  if v_referenced and new.metadata is distinct from old.metadata then
    v_old_id:=nullif(old.metadata->>'github_artifact_id','');
    v_new_id:=nullif(new.metadata->>'github_artifact_id','');
    v_old_digest:=nullif(old.metadata->>'github_artifact_digest','');
    v_new_digest:=nullif(new.metadata->>'github_artifact_digest','');
    v_old_exp:=nullif(old.metadata->>'github_artifact_expires_at','');
    v_new_exp:=nullif(new.metadata->>'github_artifact_expires_at','');
    v_old_reconciled_at:=nullif(old.metadata->>'physical_provenance_reconciled_at','');
    v_new_reconciled_at:=nullif(new.metadata->>'physical_provenance_reconciled_at','');
    v_old_source:=nullif(old.metadata->>'physical_provenance_source','');
    v_new_source:=nullif(new.metadata->>'physical_provenance_source','');

    v_old_base:=coalesce(old.metadata,'{}'::jsonb)
      -'github_artifact_id'
      -'github_artifact_digest'
      -'github_artifact_expires_at'
      -'github_head_sha'
      -'github_artifact_verified_at'
      -'physical_provenance_reconciled_at'
      -'physical_provenance_source';
    v_new_base:=coalesce(new.metadata,'{}'::jsonb)
      -'github_artifact_id'
      -'github_artifact_digest'
      -'github_artifact_expires_at'
      -'github_head_sha'
      -'github_artifact_verified_at'
      -'physical_provenance_reconciled_at'
      -'physical_provenance_source';

    if v_old_base is distinct from v_new_base then raise exception 'immutable factory artifact: release-bound metadata cannot change'; end if;

    if v_old_id is not null or v_old_digest is not null or v_old_exp is not null
       or v_old_reconciled_at is not null or v_old_source is not null then
      raise exception 'immutable factory artifact: physical provenance is write-once';
    end if;

    if v_new_id is null or v_new_id !~ '^[0-9]+$' then raise exception 'github artifact id required for physical provenance'; end if;
    if v_new_digest is null or v_new_digest !~ '^sha256:[0-9a-fA-F]{64}$' then raise exception 'github artifact digest required for physical provenance'; end if;
    if v_new_exp is null then raise exception 'github artifact expiry required for physical provenance'; end if;
    if v_new_reconciled_at is null then raise exception 'physical provenance reconciliation timestamp required'; end if;
    if v_new_source is null then raise exception 'physical provenance reconciliation source required'; end if;
  end if;

  if new.sha256 is not null and new.sha256 !~ '^[0-9a-fA-F]{64}$' then raise exception 'factory artifact sha256 must be a valid SHA-256 hex digest'; end if;
  return new;
end
$_$;


ALTER FUNCTION "private"."enforce_factory_artifact_immutability"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_product_alignment_on_factory_run"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_alignment jsonb;
  v_result jsonb;
begin
  if coalesce((new.input->>'certification_depth_run')::boolean,false) then
    return new;
  end if;

  if private.requires_product_alignment(new.app_spec_id) then
    select a.spec->'product_alignment' into v_alignment
    from public.app_specs a where a.id=new.app_spec_id;
    v_result := private.validate_product_alignment(v_alignment);
    if coalesce((v_result->>'ok')::boolean,false) is distinct from true then
      raise exception 'product alignment gate rejected App Spec: %', coalesce(v_result->>'reason','invalid_product_alignment');
    end if;
    new.input := coalesce(new.input,'{}'::jsonb) || jsonb_build_object(
      'product_alignment_enforced',true,
      'product_alignment_contract','vrs.product-alignment/1'
    );
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."enforce_product_alignment_on_factory_run"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_production_deployment_guard"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public', 'private', 'extensions', 'pg_temp'
    AS $_$
declare
  v_env_kind text; v_run public.factory_runs%rowtype; v_required jsonb; v_technical_missing int; v_human_ok boolean; v_unlock_ok boolean; v_approval_ok boolean; v_cert_hash text; v_art public.factory_artifacts%rowtype;
begin
  select kind into v_env_kind from public.environments where id=new.environment_id and project_id=new.project_id;
  if v_env_kind is distinct from 'production' then return new; end if;
  if new.status not in ('certified','approved','deploying','deployed') then return new; end if;
  if new.workflow_id is null then raise exception 'production deployment requires workflow_id'; end if;
  if new.factory_run_id is null then raise exception 'production deployment requires factory_run_id'; end if;
  select * into v_run from public.factory_runs where id=new.factory_run_id and project_id=new.project_id;
  if not found then raise exception 'production deployment requires a valid factory run'; end if;
  if new.workflow_id is distinct from v_run.workflow_id then raise exception 'production deployment workflow does not match factory run'; end if;
  v_required:=coalesce(new.required_gates_snapshot,'[]'::jsonb);
  if jsonb_array_length(v_required)=0 then raise exception 'production deployment requires frozen gate policy'; end if;
  select count(*) into v_technical_missing from jsonb_array_elements(v_required) g where not exists(select 1 from public.release_gates rg where rg.factory_run_id=v_run.id and rg.gate_key=g->>'key' and rg.status='pass');
  if v_technical_missing>0 then raise exception 'production certification blocked: frozen required gates not all PASS'; end if;
  if new.artifact_sha256 is null or new.artifact_sha256 !~ '^[0-9a-fA-F]{64}$' then raise exception 'production deployment requires valid SHA-256 artifact hash'; end if;
  v_cert_hash:=coalesce(new.certificate->>'artifact_sha256',new.certificate->>'sha256');
  if v_cert_hash is null or lower(v_cert_hash)<>lower(new.artifact_sha256) then raise exception 'production certificate hash does not match artifact SHA-256'; end if;
  if new.gate_policy_sha256 is null or lower(new.gate_policy_sha256)<>lower(encode(extensions.digest(convert_to(new.required_gates_snapshot::text,'UTF8'),'sha256'),'hex')) then raise exception 'production gate policy snapshot hash mismatch'; end if;

  if new.status in ('approved','deploying','deployed') then
    select * into v_art from public.factory_artifacts where factory_run_id=new.factory_run_id and artifact_type='bundle' and lower(sha256)=lower(new.artifact_sha256) order by created_at desc limit 1;
    if not found then raise exception 'production deployment blocked: immutable source artifact required'; end if;
    if v_art.storage_path not like 'github-actions://lundus88/fieldgis-reference/runs/%/artifacts/%' then raise exception 'production deployment blocked: trusted GitHub Actions artifact path required'; end if;
    if coalesce(v_art.metadata->>'github_artifact_id','') !~ '^[0-9]+$' then raise exception 'production deployment blocked: GitHub artifact id provenance required'; end if;
    if coalesce(v_art.metadata->>'github_artifact_digest','') !~ '^sha256:[0-9a-fA-F]{64}$' then raise exception 'production deployment blocked: GitHub artifact digest provenance required'; end if;
    if nullif(v_art.metadata->>'github_artifact_expires_at','') is null then raise exception 'production deployment blocked: GitHub artifact expiry provenance required'; end if;
    if (v_art.metadata->>'github_artifact_expires_at')::timestamptz <= now() then raise exception 'production deployment blocked: GitHub artifact has expired'; end if;
    if new.source_commit_sha is null or new.source_commit_sha !~ '^[0-9a-fA-F]{40}$' then raise exception 'production deployment blocked: valid source commit SHA required'; end if;
    if nullif(v_art.metadata->>'github_head_sha','') is null or lower(v_art.metadata->>'github_head_sha')<>lower(new.source_commit_sha) then raise exception 'production deployment blocked: GitHub artifact commit provenance mismatch'; end if;

    select exists(select 1 from public.release_gates rg where rg.factory_run_id=v_run.id and rg.gate_key='human_production_approval' and rg.status='pass') into v_human_ok;
    select exists(select 1 from public.release_gates rg where rg.factory_run_id=v_run.id and rg.gate_key='production_lock' and rg.status='pass') into v_unlock_ok;
    select exists(select 1 from public.approvals a where a.factory_run_id=v_run.id and a.project_id=new.project_id and a.workflow_id=new.workflow_id and a.approval_type='production_release' and a.status='approved' and a.decided_by is not null and a.decided_at is not null) into v_approval_ok;
    if not v_human_ok then raise exception 'production deployment blocked: human production approval gate not PASS'; end if;
    if not v_unlock_ok then raise exception 'production deployment blocked: production lock not released'; end if;
    if not v_approval_ok then raise exception 'production deployment blocked: approved human approval record required'; end if;
    if new.approved_by is null then raise exception 'production deployment blocked: approved_by required'; end if;
  end if;
  if new.status='deployed' and new.deployed_at is null then new.deployed_at:=now(); end if;
  return new;
end
$_$;


ALTER FUNCTION "private"."enforce_production_deployment_guard"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_public_factory_quota"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public', 'private', 'auth', 'pg_temp'
    AS $$
declare
  v_account public.customer_accounts%rowtype;
  v_daily_limit int;
  v_concurrent_limit int;
  v_daily_used int;
  v_active int;
  v_policy private.internal_usage_policy%rowtype;
  v_internal_daily int;
  v_internal_active int;
  v_internal_cost bigint;
  v_estimated_cost bigint;
  v_classification text;
  v_override private.internal_usage_overrides%rowtype;
begin
  if coalesce(current_setting('vrs.certification_depth_authorized', true),'')='true'
     and coalesce((new.input->>'certification_depth_run')::boolean,false)=true
     and new.target_environment='staging'
     and new.production_locked is true then
    return new;
  end if;

  if coalesce(new.input->>'build_mode','')='founder_internal' then
    if new.target_environment <> 'staging' or new.production_locked is distinct from true then
      raise exception 'founder/internal entry must be staging-only and production-locked' using errcode='42501';
    end if;
    if not exists (
      select 1 from public.project_members pm
      where pm.project_id=new.project_id and pm.user_id=new.requested_by and pm.role in ('owner','admin')
    ) then raise exception 'owner/admin founder/internal authority required' using errcode='42501'; end if;

    v_classification := nullif(new.input->>'internal_usage_classification','');
    if v_classification not in ('r_and_d','vl_maintenance','demo','customer_poc','internal_commercial_project') then
      raise exception 'valid internal usage classification required' using errcode='P0001';
    end if;
    begin v_estimated_cost := (new.input->>'estimated_cost_units')::bigint;
    exception when others then raise exception 'estimated_cost_units integer required' using errcode='P0001'; end;
    if v_estimated_cost < 0 then raise exception 'estimated_cost_units must be non-negative' using errcode='P0001'; end if;

    select * into v_policy from private.internal_usage_policy where singleton=true and enabled=true;
    if not found then raise exception 'founder/internal usage policy unavailable' using errcode='42501'; end if;

    select count(*) into v_internal_daily from private.internal_usage_ledger
      where requested_by=new.requested_by and recorded_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC';
    select coalesce(sum(estimated_cost_units),0) into v_internal_cost from private.internal_usage_ledger
      where requested_by=new.requested_by and recorded_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC';
    select count(*) into v_internal_active
      from private.runner_jobs rj join public.factory_runs fr on fr.id=rj.factory_run_id
      where fr.requested_by=new.requested_by and coalesce(fr.input->>'build_mode','')='founder_internal'
        and rj.state in ('queued','leased','running');

    if v_internal_daily >= v_policy.daily_run_limit
       or v_internal_active >= v_policy.concurrent_run_limit
       or v_internal_cost + v_estimated_cost > v_policy.daily_estimated_cost_unit_limit then
      select * into v_override from private.internal_usage_overrides o
      where o.project_id=new.project_id and o.requested_by=new.requested_by
        and o.revoked_at is null and o.valid_from<=now() and o.expires_at>now()
      order by o.created_at desc limit 1;
      if not found then raise exception 'founder/internal usage limit exceeded; explicit active override required' using errcode='P0001'; end if;
    end if;

    insert into private.internal_usage_ledger(factory_run_id,project_id,requested_by,classification,estimated_cost_units,override_id)
    values(new.id,new.project_id,new.requested_by,v_classification,v_estimated_cost,v_override.id);
    insert into private.internal_usage_audit(factory_run_id,project_id,actor_user_id,event_type,reason,evidence)
    values(new.id,new.project_id,new.requested_by,'internal_run_admitted',v_override.reason,jsonb_build_object(
      'classification',v_classification,'estimated_cost_units',v_estimated_cost,
      'daily_used_before',v_internal_daily,'concurrent_used_before',v_internal_active,
      'daily_estimated_cost_before',v_internal_cost,'override_id',v_override.id,
      'target_environment',new.target_environment,'production_locked',new.production_locked,
      'production_approval_bypassed',false,'production_promotion_bypassed',false
    ));
    return new;
  end if;

  select * into v_account from public.customer_accounts where owner_user_id=new.requested_by;
  if not found then return new; end if;
  if v_account.status<>'active' or v_account.onboarding_state<>'ready' or v_account.terms_accepted_at is null then
    raise exception 'customer account is not launch-ready' using errcode='42501';
  end if;
  select coalesce((limits->>'factory_runs_per_day')::int,0),coalesce((limits->>'concurrent_runs')::int,0)
    into v_daily_limit,v_concurrent_limit from public.plan_catalog where plan_key=v_account.plan_key and is_public=true;
  if v_daily_limit<=0 or v_concurrent_limit<=0 then raise exception 'plan quota is not configured' using errcode='42501'; end if;
  select count(*) into v_daily_used from public.factory_runs where requested_by=new.requested_by
    and created_at>=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'
    and coalesce((input->>'certification_depth_run')::boolean,false)=false
    and coalesce(input->>'build_mode','')<>'founder_internal';
  if v_daily_used>=v_daily_limit then raise exception 'daily factory run quota exceeded' using errcode='P0001'; end if;
  select count(*) into v_active from private.runner_jobs rj join public.factory_runs fr on fr.id=rj.factory_run_id
    where fr.requested_by=new.requested_by and rj.state in ('queued','leased','running')
      and coalesce((fr.input->>'certification_depth_run')::boolean,false)=false
      and coalesce(fr.input->>'build_mode','')<>'founder_internal';
  if v_active>=v_concurrent_limit then raise exception 'concurrent factory run quota exceeded' using errcode='P0001'; end if;
  insert into private.usage_counters(customer_account_id,metric_key,window_start,window_end,used_count,limit_count)
  values(v_account.id,'factory_runs',date_trunc('day',now() at time zone 'UTC') at time zone 'UTC',
    (date_trunc('day',now() at time zone 'UTC')+interval '1 day') at time zone 'UTC',v_daily_used+1,v_daily_limit)
  on conflict(customer_account_id,metric_key,window_start,window_end) do update
    set used_count=excluded.used_count,limit_count=excluded.limit_count,updated_at=now();
  return new;
end;
$$;


ALTER FUNCTION "private"."enforce_public_factory_quota"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enforce_release_identity_binding"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public', 'private', 'pg_temp'
    AS $$
begin
  if new.project_id is distinct from old.project_id
     or new.workflow_id is distinct from old.workflow_id
     or new.factory_run_id is distinct from old.factory_run_id then
    raise exception 'immutable release identity binding: project/workflow/factory run cannot change';
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."enforce_release_identity_binding"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enqueue_factory_runner_job"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_builder text;
begin
  if new.run_type not in ('build','upgrade') then return new; end if;
  if new.target_environment='production' or new.production_locked is distinct from true then return new; end if;
  if new.state not in ('queued','planning','building','validating') then return new; end if;
  if new.run_type='upgrade' and new.base_factory_run_id is null then
    raise exception 'upgrade run requires base_factory_run_id';
  end if;
  v_builder:=private.resolve_factory_builder(new.id);
  if v_builder is null then return new; end if;
  insert into private.runner_jobs(factory_run_id,project_id,builder_key)
  values(new.id,new.project_id,v_builder)
  on conflict(factory_run_id) do nothing;
  return new;
end;
$$;


ALTER FUNCTION "private"."enqueue_factory_runner_job"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enqueue_production_promotion_job"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare v_run public.factory_runs%rowtype; v_builder text; v_adapter text; v_configured boolean;
begin
 if new.status='approved' and (tg_op='INSERT' or old.status is distinct from new.status) then
   select * into v_run from public.factory_runs where id=new.factory_run_id and project_id=new.project_id;
   if not found then raise exception 'deployment factory_run_id is invalid for project'; end if;
   if new.workflow_id is distinct from v_run.workflow_id then raise exception 'deployment workflow_id does not match factory run'; end if;
   v_builder:=coalesce(v_run.result#>>'{runner,builder_key}',private.resolve_factory_builder(v_run.id));
   select adapter_key,configured into v_adapter,v_configured from private.production_adapter_registry where builder_key=v_builder;
   insert into private.production_promotion_jobs(deployment_id,project_id,factory_run_id,builder_key,artifact_sha256,target_adapter,state,error_text)
   values(new.id,new.project_id,v_run.id,v_builder,new.artifact_sha256,v_adapter,
     case when v_configured then 'queued' else 'blocked' end,
     case when v_configured then null else 'BLOCKED/UNCONFIGURED: production adapter target or credentials unavailable' end)
   on conflict(deployment_id) do nothing;
 end if;
 return new;
end $$;


ALTER FUNCTION "private"."enqueue_production_promotion_job"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enqueue_release_validation_job"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare v_run public.factory_runs%rowtype; v_builder text;
begin
 if new.status='planned' and (tg_op='INSERT' or old.status is distinct from new.status) then
   select * into v_run from public.factory_runs where id=new.factory_run_id and project_id=new.project_id;
   if not found then raise exception 'deployment factory_run_id is invalid for project'; end if;
   if new.workflow_id is distinct from v_run.workflow_id then raise exception 'deployment workflow_id does not match factory run'; end if;
   v_builder:=coalesce(v_run.result#>>'{runner,builder_key}',private.resolve_factory_builder(v_run.id));
   if v_builder is not null then
     insert into private.release_validation_jobs(deployment_id,factory_run_id,project_id,builder_key)
     values(new.id,v_run.id,new.project_id,v_builder)
     on conflict(deployment_id) do nothing;
   end if;
 end if;
 return new;
end $$;


ALTER FUNCTION "private"."enqueue_release_validation_job"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."enrich_factory_run_capability_plan"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_compilation_id uuid;
  v_adapters jsonb;
  v_blockers jsonb;
begin
  begin
    v_compilation_id := nullif(new.input->>'compilation_id','')::uuid;
  exception when others then
    v_compilation_id := null;
  end;

  if v_compilation_id is not null then
    select capability_adapter_plan
      into v_adapters
      from public.spec_compilations
     where id = v_compilation_id;

    if v_adapters is not null then
      select coalesce(jsonb_agg(x), '[]'::jsonb)
        into v_blockers
        from jsonb_array_elements(v_adapters) x
       where coalesce((x->>'blocking')::boolean, false) = true;

      if jsonb_array_length(v_blockers) > 0 then
        raise exception using
          errcode = 'P0001',
          message = 'CAPABILITY_ADAPTER_BLOCKED: one or more required capability adapters are unavailable',
          detail = v_blockers::text,
          hint = 'Configure and certify the missing capability adapter before planning a factory run.';
      end if;

      new.plan := coalesce(new.plan,'{}'::jsonb)
        || jsonb_build_object('capability_adapters', v_adapters);
    end if;
  end if;

  return new;
end;
$$;


ALTER FUNCTION "private"."enrich_factory_run_capability_plan"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."ensure_default_project_environments"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  insert into public.environments(project_id,name,kind,status,metadata)
  select new.id,v.name,v.kind,'ready',jsonb_build_object(
    'provisioning','logical_default',
    'provider_binding','required_before_promotion'
  )
  from (values
    ('development'::text,'development'::text),
    ('staging'::text,'staging'::text),
    ('production'::text,'production'::text)
  ) as v(name,kind)
  where not exists (
    select 1 from public.environments e
    where e.project_id=new.id and e.kind=v.kind
  );
  return new;
end;
$$;


ALTER FUNCTION "private"."ensure_default_project_environments"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."ensure_release_candidate"("p_factory_run_id" "uuid", "p_actor" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $_$
declare
  v_run public.factory_runs%rowtype;
  v_env public.environments%rowtype;
  v_sha text; v_dep_id uuid; v_approval_id uuid; v_version text; v_required jsonb; g jsonb;
  v_builder text; v_builder_version integer; v_policy_version integer; v_profile_hash text; v_effective_hash text; v_app_spec_hash text;
begin
  if p_actor is null then raise exception 'release candidate actor required'; end if;
  select * into v_run from public.factory_runs where id=p_factory_run_id for update;
  if not found then raise exception 'factory run not found'; end if;
  if not exists(select 1 from public.project_members pm where pm.project_id=v_run.project_id and pm.user_id=p_actor and pm.role in ('owner','admin','builder')) then raise exception 'actor is not authorized project member'; end if;
  if v_run.state<>'validating' or v_run.target_environment<>'staging' or v_run.production_locked is not true then raise exception 'release candidate requires locked staging run in validating state'; end if;
  if coalesce(v_run.result->>'runner_status','')<>'PASS' then raise exception 'runner QA PASS required'; end if;
  v_sha:=coalesce(v_run.result#>>'{runner,artifact_sha256}',v_run.result->>'artifact_sha256');
  if v_sha is null or v_sha !~ '^[0-9a-fA-F]{64}$' then raise exception 'valid runner artifact SHA-256 required'; end if;
  if v_run.workflow_id is null then raise exception 'workflow_id required'; end if;

  select * into v_env from public.environments where project_id=v_run.project_id and kind='production' and status='ready' order by created_at desc limit 1;
  if not found then return jsonb_build_object('decision','blocked','reason','ready_production_environment_required','factory_run_id',v_run.id); end if;

  v_builder:=coalesce(v_run.result#>>'{runner,builder_key}',private.resolve_factory_builder(v_run.id));
  select coalesce(br.version,1) into v_builder_version from public.builder_registry br where br.builder_key=v_builder;
  select coalesce(p.policy_version,1),p.policy_sha256 into v_policy_version,v_profile_hash from private.builder_release_gate_profiles p where p.builder_key=v_builder;
  v_required:=private.get_required_release_gates(v_run.id);
  v_effective_hash:=encode(digest(convert_to(v_required::text,'UTF8'),'sha256'),'hex');
  select encode(digest(convert_to(jsonb_build_object('version',a.version,'title',a.title,'objective',a.objective,'software_kind',a.software_kind,'target_platforms',a.target_platforms,'spec',a.spec)::text,'UTF8'),'sha256'),'hex') into v_app_spec_hash from public.app_specs a where a.id=v_run.app_spec_id;

  for g in select value from jsonb_array_elements(v_required) loop
    insert into public.release_gates(project_id,factory_run_id,gate_key,gate_type,status,evidence,score,checked_at)
    values(v_run.project_id,v_run.id,g->>'key',g->>'type',case when g->>'key'='qa_regression' then 'pass' else 'pending' end,
      case when g->>'key'='qa_regression' then jsonb_build_object('runner','github-actions-oidc','runner_status','PASS','artifact_sha256',v_sha,'github_run_id',v_run.result#>>'{runner,github_run_id}') else '{}'::jsonb end,
      case when g->>'key'='qa_regression' then 1 else null end,case when g->>'key'='qa_regression' then now() else null end)
    on conflict(factory_run_id,gate_key) do update set
      status=case when excluded.gate_key='qa_regression' then 'pass' else public.release_gates.status end,
      evidence=case when excluded.gate_key='qa_regression' then excluded.evidence else public.release_gates.evidence end,
      score=case when excluded.gate_key='qa_regression' then 1 else public.release_gates.score end,
      checked_at=case when excluded.gate_key='qa_regression' then now() else public.release_gates.checked_at end;
  end loop;
  insert into public.release_gates(project_id,factory_run_id,gate_key,gate_type,status,evidence)
  values(v_run.project_id,v_run.id,'human_production_approval','human_approval','pending','{}'::jsonb),(v_run.project_id,v_run.id,'production_lock','production_lock','pending','{}'::jsonb)
  on conflict(factory_run_id,gate_key) do nothing;

  v_version:='vl-'||to_char(clock_timestamp(),'YYYYMMDDHH24MISS')||'-'||left(v_sha,8);
  insert into public.deployments(project_id,environment_id,workflow_id,factory_run_id,release_version,status,artifact_sha256,certificate,created_by)
  values(v_run.project_id,v_env.id,v_run.workflow_id,v_run.id,v_version,'planned',v_sha,
    jsonb_build_object('schema','vrs.release-certificate/3','factory_run_id',v_run.id,'artifact_sha256',v_sha,'builder_key',v_builder,'builder_version',coalesce(v_builder_version,1),'runner_qa','PASS','production_locked',true,'required_gates',v_required,'gate_policy_version',coalesce(v_policy_version,1),'gate_policy_sha256',v_effective_hash,'builder_profile_sha256',v_profile_hash,'app_spec_sha256',v_app_spec_hash,'source_commit_sha',coalesce(v_run.result#>>'{runner,commit_sha}',v_run.result#>>'{runner,github_sha}')),p_actor)
  on conflict(factory_run_id,environment_id) do nothing;

  select id into v_dep_id from public.deployments where factory_run_id=v_run.id and environment_id=v_env.id limit 1;
  if v_dep_id is null then raise exception 'release deployment could not be resolved idempotently'; end if;

  insert into public.approvals(project_id,workflow_id,factory_run_id,approval_type,status,requested_by,rationale)
  values(v_run.project_id,v_run.workflow_id,v_run.id,'production_release','pending',p_actor,'Autonomous staging build passed runner QA. Technical release gates must pass before explicit production approval.')
  on conflict(factory_run_id,approval_type) do nothing;

  select id into v_approval_id from public.approvals where factory_run_id=v_run.id and approval_type='production_release' limit 1;
  if v_approval_id is null then raise exception 'production approval could not be resolved idempotently'; end if;

  return jsonb_build_object('decision','release_candidate_prepared','factory_run_id',v_run.id,'deployment_id',v_dep_id,'approval_id',v_approval_id,'artifact_sha256',v_sha,'required_gates',v_required,'deployment_status','planned','human_approval','pending','production_locked',true);
end $_$;


ALTER FUNCTION "private"."ensure_release_candidate"("p_factory_run_id" "uuid", "p_actor" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."evaluate_factory_preflight"("p_compilation_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_plan jsonb;
  v_blockers jsonb;
  v_blocker_count integer;
  v_project_id uuid;
  v_app_spec_id uuid;
begin
  select project_id, app_spec_id, capability_adapter_plan
    into v_project_id, v_app_spec_id, v_plan
  from public.spec_compilations
  where id = p_compilation_id;

  if not found then
    return jsonb_build_object(
      'ready', false,
      'decision', 'BLOCKED',
      'reason', 'compilation_not_found',
      'production_locked', true
    );
  end if;

  v_plan := coalesce(v_plan, '[]'::jsonb);

  select coalesce(jsonb_agg(x), '[]'::jsonb), count(*)
    into v_blockers, v_blocker_count
  from jsonb_array_elements(v_plan) x
  where coalesce((x->>'blocking')::boolean, false) = true
     or coalesce(x->>'resolution','') = 'missing';

  return jsonb_build_object(
    'ready', v_blocker_count = 0,
    'decision', case when v_blocker_count = 0 then 'READY_FOR_FACTORY' else 'BLOCKED' end,
    'compilation_id', p_compilation_id,
    'project_id', v_project_id,
    'app_spec_id', v_app_spec_id,
    'production_locked', true,
    'adapter_plan', v_plan,
    'blocker_count', v_blocker_count,
    'blockers', v_blockers
  );
end;
$$;


ALTER FUNCTION "private"."evaluate_factory_preflight"("p_compilation_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."fulfill_verified_sandbox_payment"("p_order_id" "uuid", "p_action_key" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'pg_temp'
    AS $$
declare
  o private.payment_sandbox_orders%rowtype;
  valid_evidence boolean := false;
  prior private.payment_fulfillment_events%rowtype;
begin
  if p_action_key is null or length(trim(p_action_key)) < 8 then
    raise exception 'invalid action key';
  end if;

  select * into o from private.payment_sandbox_orders where id=p_order_id for update;
  if not found then raise exception 'order not found'; end if;

  select * into prior from private.payment_fulfillment_events where action_key=p_action_key;
  if found then
    return jsonb_build_object('ok', prior.status='fulfilled', 'duplicate', true, 'status', prior.status, 'order_id', p_order_id);
  end if;

  if o.environment <> 'sandbox' or o.adapter_key <> 'billplz-payment-v1' then
    raise exception 'sandbox billplz order required';
  end if;
  if o.status <> 'paid' or o.paid_at is null then
    raise exception 'payment not verified';
  end if;
  if o.fulfillment_state = 'fulfilled' then
    return jsonb_build_object('ok', true, 'duplicate', true, 'status', 'fulfilled', 'order_id', p_order_id);
  end if;
  if o.fulfillment_state <> 'unfulfilled' then
    raise exception 'invalid fulfillment state';
  end if;

  select exists(
    select 1 from private.payment_webhook_events e
    where e.provider_bill_id=o.provider_bill_id
      and e.adapter_key='billplz-payment-v1'
      and e.signature_valid=true
      and e.normalized_status='paid'
      and e.amount_minor=o.amount_minor
      and e.applied=true
      and coalesce(e.error_text,'')=''
  ) into valid_evidence;
  if not valid_evidence then raise exception 'signed paid webhook evidence required'; end if;

  update private.payment_sandbox_orders
     set fulfillment_state='fulfilled', updated_at=now()
   where id=o.id and fulfillment_state='unfulfilled';
  if not found then raise exception 'fulfillment race blocked'; end if;

  insert into private.payment_fulfillment_events(order_id,adapter_key,action_key,status,evidence)
  values(o.id,o.adapter_key,p_action_key,'fulfilled',jsonb_build_object(
    'provider_bill_id',o.provider_bill_id,
    'amount_minor',o.amount_minor,
    'currency',o.currency,
    'payment_status',o.status,
    'signed_webhook_required',true,
    'environment','sandbox'
  ));

  return jsonb_build_object('ok',true,'duplicate',false,'status','fulfilled','order_id',o.id);
end;
$$;


ALTER FUNCTION "private"."fulfill_verified_sandbox_payment"("p_order_id" "uuid", "p_action_key" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."get_deployment_required_gates"("p_deployment_id" "uuid") RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
  select coalesce(d.required_gates_snapshot,'[]'::jsonb)
  from public.deployments d
  where d.id=p_deployment_id
$$;


ALTER FUNCTION "private"."get_deployment_required_gates"("p_deployment_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."get_deployment_required_release_gates"("p_deployment_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_factory_run_id uuid;
begin
  select d.factory_run_id into v_factory_run_id
  from public.deployments d
  where d.id = p_deployment_id;

  if v_factory_run_id is null then
    raise exception 'deployment not found';
  end if;

  return private.get_required_release_gates(v_factory_run_id);
end;
$$;


ALTER FUNCTION "private"."get_deployment_required_release_gates"("p_deployment_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."get_required_release_gates"("p_factory_run_id" "uuid") RETURNS "jsonb"
    LANGUAGE "sql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
  with ctx as (
    select
      fr.run_type,
      coalesce(fr.result#>>'{runner,builder_key}', private.resolve_factory_builder(fr.id)) as builder_key,
      coalesce(a.spec,'{}'::jsonb) as spec
    from public.factory_runs fr
    left join public.app_specs a on a.id=fr.app_spec_id
    where fr.id=p_factory_run_id
  ), base as (
    select c.run_type,c.spec,
           coalesce(p.required_gates,
             '[{"key":"security_advisor","type":"security"},{"key":"cross_tenant_rls","type":"rls"},{"key":"auth_http_e2e","type":"auth"},{"key":"data_api_http_e2e","type":"data_api"},{"key":"storage_physical_e2e","type":"storage"},{"key":"rollback_rehearsal","type":"rollback"},{"key":"qa_regression","type":"qa"}]'::jsonb
           ) as gates
    from ctx c
    left join private.builder_release_gate_profiles p using(builder_key)
  ), filtered as (
    select b.run_type,jsonb_agg(g.value order by g.ord) as gates
    from base b,
         lateral jsonb_array_elements(b.gates) with ordinality as g(value,ord)
    where not (
      (g.value->>'key'='auth_http_e2e' and ((b.spec ? 'auth' and b.spec->'auth'='false'::jsonb) or coalesce((b.spec#>>'{inferred,auth_requested}')::boolean,false)=false))
      or (g.value->>'key'='storage_physical_e2e' and b.spec ? 'storage' and b.spec->'storage'='false'::jsonb)
      or (g.value->>'key' in ('cross_tenant_rls','data_api_http_e2e') and not exists (
          select 1 from jsonb_array_elements_text(coalesce(b.spec#>'{inferred,required_capabilities}','[]'::jsonb)) c(value) where c.value='supabase'))
      or (g.value->>'key' in ('cross_tenant_rls','data_api_http_e2e') and coalesce((b.spec#>>'{constraints,demo_data_only}')::boolean,false)=true and jsonb_array_length(coalesce(b.spec->'entities','[]'::jsonb))=0)
    )
    group by b.run_type
  )
  select coalesce(f.gates,'[]'::jsonb) ||
         case when f.run_type='upgrade'
              then '[{"key":"upgrade_lineage_contract","type":"qa"}]'::jsonb
              else '[]'::jsonb end
  from filtered f
$$;


ALTER FUNCTION "private"."get_required_release_gates"("p_factory_run_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."guard_customer_account_mutation"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public', 'private', 'auth', 'pg_temp'
    AS $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role',true),'');
begin
  if v_role='authenticated' then
    if tg_op='INSERT' then
      if new.owner_user_id is distinct from auth.uid() then raise exception 'owner mismatch' using errcode='42501'; end if;
      if new.plan_key <> 'launch_pilot' then raise exception 'plan not self-selectable' using errcode='42501'; end if;
      if new.status not in ('pending','active') then raise exception 'invalid initial account status' using errcode='42501'; end if;
      if new.status='active' and (new.terms_accepted_at is null or new.onboarding_state<>'ready') then raise exception 'active account requires accepted terms and ready onboarding' using errcode='42501'; end if;
    elsif tg_op='UPDATE' then
      if new.owner_user_id is distinct from old.owner_user_id or new.plan_key is distinct from old.plan_key or new.status is distinct from old.status then
        raise exception 'sensitive account fields are operator-controlled' using errcode='42501';
      end if;
    end if;
  end if;
  new.updated_at:=now();
  return new;
end $$;


ALTER FUNCTION "private"."guard_customer_account_mutation"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."guard_factory_awaiting_approval_requires_certified_deployment"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  if new.state='awaiting_approval' and (old.state is distinct from new.state) then
    if not exists (
      select 1 from public.deployments d
      where d.project_id=new.project_id
        and d.workflow_id=new.workflow_id
        and d.status='certified'
        and d.artifact_sha256 is not null
        and length(d.artifact_sha256)=64
    ) then
      raise exception 'awaiting_approval requires a certified deployment with immutable artifact SHA-256';
    end if;
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."guard_factory_awaiting_approval_requires_certified_deployment"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."guard_supply_chain_attestation_gate"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  if new.gate_key = 'supply_chain_attestation'
     and new.status = 'pass'
     and old.status is distinct from 'pass'
     and coalesce(current_setting('vrs.supply_chain_authorized', true), '') <> 'true' then
    raise exception 'supply_chain_attestation PASS requires dedicated attestation authority';
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."guard_supply_chain_attestation_gate"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."has_org_role"("p_org" "uuid", "p_roles" "text"[], "p_user" "uuid" DEFAULT "auth"."uid"()) RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public', 'private'
    AS $$
  select p_user is not null and exists (
    select 1 from public.organization_members m
    where m.organization_id = p_org and m.user_id = p_user and m.role = any(p_roles)
  );
$$;


ALTER FUNCTION "private"."has_org_role"("p_org" "uuid", "p_roles" "text"[], "p_user" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."has_project_role"("p_project" "uuid", "p_roles" "text"[], "p_user" "uuid" DEFAULT "auth"."uid"()) RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public', 'private'
    AS $$
  select p_user is not null and exists (
    select 1 from public.project_members pm where pm.project_id = p_project and pm.user_id = p_user and pm.role = any(p_roles)
  );
$$;


ALTER FUNCTION "private"."has_project_role"("p_project" "uuid", "p_roles" "text"[], "p_user" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."is_org_member"("p_org" "uuid", "p_user" "uuid" DEFAULT "auth"."uid"()) RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public', 'private'
    AS $$
  select p_user is not null and exists (
    select 1 from public.organization_members m
    where m.organization_id = p_org and m.user_id = p_user
  );
$$;


ALTER FUNCTION "private"."is_org_member"("p_org" "uuid", "p_user" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."is_project_member"("p_project" "uuid", "p_user" "uuid" DEFAULT "auth"."uid"()) RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public', 'private'
    AS $$
  select p_user is not null and exists (
    select 1 from public.project_members pm where pm.project_id = p_project and pm.user_id = p_user
  );
$$;


ALTER FUNCTION "private"."is_project_member"("p_project" "uuid", "p_user" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."mark_factory_build_started"("p_factory_run_id" "uuid", "p_adapter_metadata" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare r public.factory_runs%rowtype;
begin
  select * into r from public.factory_runs where id=p_factory_run_id for update;
  if not found then raise exception 'Factory run not found'; end if;
  if r.state <> 'planning' then raise exception 'Factory run must be planning'; end if;
  update public.factory_runs set state='building', result=coalesce(result,'{}'::jsonb)||jsonb_build_object('adapter',p_adapter_metadata) where id=r.id;
  insert into private.factory_execution_events(factory_run_id,project_id,event_type,from_state,to_state,payload)
  values(r.id,r.project_id,'build_started','planning','building',p_adapter_metadata);
  return jsonb_build_object('decision','building','state','building');
end;
$$;


ALTER FUNCTION "private"."mark_factory_build_started"("p_factory_run_id" "uuid", "p_adapter_metadata" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."normalize_generated_mobile_source"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $_$
begin
  if new.path='mobile/flutter/lib/field_point.dart' then
    new.content:=replace(new.content,$old$(j['accuracy_m'] as num? ?? 0).toDouble()$old$,$new$((j['accuracy_m'] as num?) ?? 0).toDouble()$new$);
    new.sha256:=encode(extensions.digest(new.content,'sha256'),'hex');
    new.metadata:=coalesce(new.metadata,'{}'::jsonb)||jsonb_build_object('source_normalizer','mobile-v2.0.1');
  end if;
  return new;
end
$_$;


ALTER FUNCTION "private"."normalize_generated_mobile_source"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."notification_production_readiness"() RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
select jsonb_build_object(
  'adapter_key',r.adapter_key,
  'adapter_status',r.status,
  'production_send_allowed',coalesce((r.capabilities->>'production_send_allowed')::boolean,false) and coalesce((r.configuration->>'production_send_allowed')::boolean,false),
  'sandbox_e2e_verified_at',r.configuration->>'sandbox_e2e_verified_at',
  'sandbox_reconciliation_verified_at',r.configuration->>'sandbox_reconciliation_verified_at'
)
from private.capability_adapter_registry r where r.adapter_key='resend-email-v1';
$$;


ALTER FUNCTION "private"."notification_production_readiness"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."prepare_factory_execution"("p_factory_run_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  r public.factory_runs%rowtype;
  a public.app_specs%rowtype;
  v_builder_key text;
  v_builder public.builder_registry%rowtype;
  v_dispatch jsonb;
begin
  select * into r from public.factory_runs where id=p_factory_run_id for update;
  if not found then raise exception 'Factory run not found'; end if;
  if r.state <> 'queued' then raise exception 'Factory run must be queued'; end if;
  if r.target_environment = 'production' or r.production_locked is distinct from true then
    raise exception 'Factory execution v1 only allows production-locked non-production runs';
  end if;
  if r.app_spec_id is null then raise exception 'Factory run requires app spec'; end if;

  select * into a from public.app_specs where id=r.app_spec_id;
  if not found or a.status <> 'approved' then raise exception 'Approved App Spec required'; end if;

  v_builder_key := coalesce(a.spec #>> '{selected_builder,builder_key}', a.spec #>> '{routing,selected_builder,builder_key}');
  if v_builder_key is null then raise exception 'Approved App Spec has no selected builder'; end if;

  select * into v_builder from public.builder_registry where builder_key=v_builder_key and status='active';
  if not found then raise exception 'Selected builder is not active'; end if;

  v_dispatch := jsonb_build_object(
    'contract_version','1.0',
    'factory_run_id',r.id,
    'project_id',r.project_id,
    'app_spec_id',r.app_spec_id,
    'builder_key',v_builder.builder_key,
    'runtime',v_builder.runtime,
    'targets',v_builder.targets,
    'target_environment',r.target_environment,
    'production_locked',r.production_locked,
    'spec',a.spec
  );

  update public.factory_runs
  set state='planning', started_at=coalesce(started_at,now()),
      plan = coalesce(plan,'{}'::jsonb) || jsonb_build_object('dispatch',v_dispatch,'execution_engine','v1')
  where id=r.id;

  update public.workflows set state='running', started_at=coalesce(started_at,now()) where id=r.workflow_id and state='queued';

  insert into private.factory_execution_events(factory_run_id,project_id,event_type,from_state,to_state,payload)
  values(r.id,r.project_id,'prepared','queued','planning',v_dispatch);

  return jsonb_build_object('decision','prepared','dispatch',v_dispatch,'state','planning');
end;
$$;


ALTER FUNCTION "private"."prepare_factory_execution"("p_factory_run_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."prepare_release_candidate"("p_factory_run_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare v_uid uuid:=auth.uid(); v_project uuid;
begin
 if v_uid is null then raise exception 'authenticated user required'; end if;
 select project_id into v_project from public.factory_runs where id=p_factory_run_id;
 if v_project is null then raise exception 'factory run not found'; end if;
 if not private.has_project_role(v_project,array['owner','admin','builder']) then raise exception 'insufficient project role'; end if;
 return private.ensure_release_candidate(p_factory_run_id,v_uid);
end $$;


ALTER FUNCTION "private"."prepare_release_candidate"("p_factory_run_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."reconcile_notification_outbox"("p_outbox_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_outbox private.notification_outbox%rowtype;
  v_provider_status text;
  v_check_status text;
  v_event_count int;
  v_signature_ok boolean;
begin
  select * into v_outbox from private.notification_outbox where id=p_outbox_id;
  if not found then raise exception 'outbox not found'; end if;
  if v_outbox.provider_message_id is null then raise exception 'provider message id missing'; end if;

  select count(*), coalesce(bool_and(signature_valid),false)
    into v_event_count,v_signature_ok
  from private.notification_events
  where adapter_key=v_outbox.adapter_key and provider_message_id=v_outbox.provider_message_id;

  select case
    when exists(select 1 from private.notification_events where adapter_key=v_outbox.adapter_key and provider_message_id=v_outbox.provider_message_id and signature_valid and event_type='email.bounced') then 'bounced'
    when exists(select 1 from private.notification_events where adapter_key=v_outbox.adapter_key and provider_message_id=v_outbox.provider_message_id and signature_valid and event_type='email.delivered') then 'delivered'
    when exists(select 1 from private.notification_events where adapter_key=v_outbox.adapter_key and provider_message_id=v_outbox.provider_message_id and signature_valid and event_type='email.sent') then 'sent'
    else null end into v_provider_status;

  v_check_status := case when v_event_count>0 and v_signature_ok and v_provider_status=v_outbox.status then 'pass' else 'fail' end;

  insert into private.notification_reconciliation_checks(adapter_key,outbox_id,expected_status,provider_status,status,evidence,checked_at)
  values(v_outbox.adapter_key,v_outbox.id,v_outbox.status,v_provider_status,v_check_status,
    jsonb_build_object('provider_message_id',v_outbox.provider_message_id,'signed_event_count',v_event_count,'all_signatures_valid',v_signature_ok,'environment',v_outbox.environment),now());

  return jsonb_build_object('outbox_id',v_outbox.id,'status',v_check_status,'expected_status',v_outbox.status,'provider_status',v_provider_status);
end $$;


ALTER FUNCTION "private"."reconcile_notification_outbox"("p_outbox_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."record_factory_artifact"("p_factory_run_id" "uuid", "p_artifact_type" "text", "p_name" "text", "p_storage_path" "text" DEFAULT NULL::"text", "p_sha256" "text" DEFAULT NULL::"text", "p_metadata" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "uuid"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare r public.factory_runs%rowtype; v_id uuid;
begin
  select * into r from public.factory_runs where id=p_factory_run_id;
  if not found then raise exception 'Factory run not found'; end if;
  if r.state not in ('building','validating') then raise exception 'Artifacts may only be recorded during building/validating'; end if;
  insert into public.factory_artifacts(factory_run_id,project_id,artifact_type,name,storage_path,sha256,metadata)
  values(r.id,r.project_id,p_artifact_type,p_name,p_storage_path,p_sha256,p_metadata)
  returning id into v_id;
  insert into private.factory_execution_events(factory_run_id,project_id,event_type,from_state,to_state,payload)
  values(r.id,r.project_id,'artifact_recorded',r.state,r.state,jsonb_build_object('artifact_id',v_id,'artifact_type',p_artifact_type,'name',p_name));
  return v_id;
end;
$$;


ALTER FUNCTION "private"."record_factory_artifact"("p_factory_run_id" "uuid", "p_artifact_type" "text", "p_name" "text", "p_storage_path" "text", "p_sha256" "text", "p_metadata" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."refresh_builder_gate_profile_version"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $$
begin
  if tg_op='INSERT' then
    new.policy_version := coalesce(new.policy_version,1);
  elsif new.required_gates is distinct from old.required_gates then
    new.policy_version := old.policy_version + 1;
  else
    new.policy_version := old.policy_version;
  end if;
  new.policy_sha256 := encode(extensions.digest(convert_to(new.required_gates::text,'UTF8'),'sha256'),'hex');
  new.updated_at := now();
  return new;
end;
$$;


ALTER FUNCTION "private"."refresh_builder_gate_profile_version"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."reject_generated_artifact_secrets"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'pg_catalog', 'public'
    AS $$
begin
  if new.content ~* '(SUPABASE_SERVICE_ROLE_KEY|sb_secret_[A-Za-z0-9_-]+|sk-proj-[A-Za-z0-9_-]+|OPENAI_API_KEY\s*=|BEGIN[[:space:]]+(RSA |EC |OPENSSH )?PRIVATE KEY)' then
    raise exception 'Generated artifact rejected: potential secret material detected';
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."reject_generated_artifact_secrets"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."reject_production_release"("p_deployment_id" "uuid", "p_rationale" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_uid uuid:=auth.uid();
  v_dep public.deployments%rowtype;
  v_run public.factory_runs%rowtype;
  v_approval public.approvals%rowtype;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  select * into v_dep from public.deployments where id=p_deployment_id for update;
  if not found then raise exception 'deployment not found'; end if;
  if not private.has_project_role(v_dep.project_id,array['owner','admin']) then raise exception 'owner/admin production decision required'; end if;
  select * into v_run from public.factory_runs where id=v_dep.factory_run_id and project_id=v_dep.project_id for update;
  if not found then raise exception 'factory run not found'; end if;
  select * into v_approval from public.approvals where factory_run_id=v_run.id and approval_type='production_release' for update;
  if found and v_approval.status='rejected' then
    return jsonb_build_object('decision','production_release_already_rejected','deployment_id',v_dep.id,'factory_run_id',v_run.id,'approval_id',v_approval.id,'idempotent',true);
  end if;
  if v_dep.status not in ('planned','certified') then raise exception 'deployment is not awaiting production decision'; end if;
  if found then
    if v_approval.status<>'pending' then raise exception 'production approval is not pending'; end if;
    update public.approvals set status='rejected',decided_by=v_uid,decided_at=now(),rationale=coalesce(nullif(p_rationale,''),'Production release rejected') where id=v_approval.id;
  end if;
  update public.release_gates set status='blocked',score=0,evidence=jsonb_build_object('rejected_by',v_uid,'rejected_at',now(),'rationale',coalesce(p_rationale,'Production release rejected')),checked_at=now(),checked_by=v_uid where factory_run_id=v_run.id and gate_key in ('human_production_approval','production_lock');
  update public.deployments set status='failed',approved_by=null,certificate=certificate||jsonb_build_object('human_approval','REJECTED','rejected_by',v_uid,'rejected_at',now(),'rationale',coalesce(p_rationale,'Production release rejected')) where id=v_dep.id;
  return jsonb_build_object('decision','production_release_rejected','deployment_id',v_dep.id,'factory_run_id',v_run.id,'approval_id',v_approval.id,'idempotent',false);
end $$;


ALTER FUNCTION "private"."reject_production_release"("p_deployment_id" "uuid", "p_rationale" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."request_production_rollback"("p_deployment_id" "uuid", "p_reason" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  d public.deployments%rowtype;
  prev public.deployments%rowtype;
  v_id uuid;
  v_adapter text;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for production rollback authorization'; end if;

  select * into d from public.deployments where id=p_deployment_id for update;
  if not found then raise exception 'deployment not found'; end if;
  if not private.has_project_role(d.project_id,array['owner','admin']) then raise exception 'owner/admin rollback authorization required'; end if;

  select * into prev from public.deployments x where x.project_id=d.project_id and x.id<>d.id and x.status in ('deployed','rolled_back')
    and x.certificate->>'technical_validation'='PASS' and x.artifact_sha256 is not null
    and coalesce(x.certificate->>'provider_deployment_id',x.certificate->>'provider_url') is not null
    order by x.deployed_at desc nulls last limit 1;

  if not found then
    insert into private.production_rollback_audits(deployment_id,requested_by,state,reason,evidence)
    values(d.id,v_uid,'blocked',coalesce(p_reason,'rollback requested'),jsonb_build_object('blocker','previous certified provider deployment required','authenticator_assurance_level',v_aal,'mfa_enforced',true)) returning id into v_id;
    return jsonb_build_object('status','BLOCKED','rollback_audit_id',v_id,'reason','previous certified provider deployment required','authenticator_assurance_level',v_aal,'mfa_enforced',true);
  end if;

  v_adapter:=coalesce(d.certificate->>'promotion_adapter',d.certificate#>>'{promotion,adapter}');
  insert into private.production_rollback_audits(deployment_id,previous_deployment_id,requested_by,state,target_adapter,provider_deployment_id,artifact_sha256,reason,evidence)
  values(d.id,prev.id,v_uid,'pending',v_adapter,coalesce(prev.certificate->>'provider_deployment_id',prev.certificate->>'provider_url'),prev.artifact_sha256,p_reason,
    jsonb_build_object('deterministic_target',true,'previous_release_version',prev.release_version,'history_preserved',true,'authenticator_assurance_level',v_aal,'mfa_enforced',true)) returning id into v_id;

  update public.deployments
  set certificate=certificate||jsonb_build_object('rollback_state','pending','rollback_audit_id',v_id,'rollback_target_deployment_id',prev.id,'rollback_authorization_aal',v_aal,'rollback_mfa_enforced',true)
  where id=d.id;

  return jsonb_build_object('status','PENDING','rollback_audit_id',v_id,'previous_deployment_id',prev.id,'artifact_sha256',prev.artifact_sha256,'authenticator_assurance_level',v_aal,'mfa_enforced',true);
end
$$;


ALTER FUNCTION "private"."request_production_rollback"("p_deployment_id" "uuid", "p_reason" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."request_vrs_internal_usage_override_impl"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "private"."request_vrs_internal_usage_override_impl"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."request_vrs_internal_usage_override_impl"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer DEFAULT 60) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "private"."request_vrs_internal_usage_override_impl"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."requires_product_alignment"("p_app_spec_id" "uuid") RETURNS boolean
    LANGUAGE "sql" STABLE
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
  select coalesce((
    select p.enabled and a.created_at >= p.activated_at
    from public.app_specs a
    cross join private.product_alignment_policy p
    where a.id = p_app_spec_id and p.policy_key='default'
  ), false)
$$;


ALTER FUNCTION "private"."requires_product_alignment"("p_app_spec_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."resolve_capability_adapter_plan"("p_normalized_spec" "jsonb", "p_module_plan" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_plan jsonb := '[]'::jsonb;
  v_auth boolean := coalesce((p_normalized_spec->>'auth')::boolean, true);
  v_storage boolean := coalesce((p_normalized_spec->>'storage')::boolean, false)
    or exists (select 1 from jsonb_array_elements(coalesce(p_module_plan,'[]'::jsonb)) m where m->>'type'='storage');
  v_database boolean := exists (select 1 from jsonb_array_elements(coalesce(p_module_plan,'[]'::jsonb)) m where m->>'type'='database');
  v_billing boolean := coalesce((p_normalized_spec->>'billing')::boolean, false);
  v_notification boolean := exists (select 1 from jsonb_array_elements(coalesce(p_module_plan,'[]'::jsonb)) m where m->>'type'='notification')
    or lower(coalesce(p_normalized_spec->'features','[]'::jsonb)::text || ' ' || coalesce(p_normalized_spec->'integrations','[]'::jsonb)::text || ' ' || coalesce(p_normalized_spec->'workflows','[]'::jsonb)::text) ~ '(notification|notify|email|resend)';
  r record;
begin
  if v_database then
    select adapter_key,provider,version,status,required_gates into r
    from private.capability_adapter_registry
    where adapter_type='database' and status in ('candidate','active')
    order by case status when 'active' then 0 else 1 end, updated_at desc limit 1;
    if found then
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','database','adapter_key',r.adapter_key,'provider',r.provider,'version',r.version,'adapter_status',r.status,'required_gates',r.required_gates,'resolution','resolved'));
    else
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','database','resolution','missing','blocking',true,'reason','No certified/candidate database adapter available'));
    end if;
  end if;

  if v_auth then
    select adapter_key,provider,version,status,required_gates into r
    from private.capability_adapter_registry
    where adapter_type='auth' and status in ('candidate','active')
    order by case status when 'active' then 0 else 1 end, updated_at desc limit 1;
    if found then
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','auth','adapter_key',r.adapter_key,'provider',r.provider,'version',r.version,'adapter_status',r.status,'required_gates',r.required_gates,'resolution','resolved'));
    else
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','auth','resolution','missing','blocking',true));
    end if;
  end if;

  if v_storage then
    select adapter_key,provider,version,status,required_gates into r
    from private.capability_adapter_registry
    where adapter_type='storage' and status in ('candidate','active')
    order by case status when 'active' then 0 else 1 end, updated_at desc limit 1;
    if found then
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','storage','adapter_key',r.adapter_key,'provider',r.provider,'version',r.version,'adapter_status',r.status,'required_gates',r.required_gates,'resolution','resolved'));
    else
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','storage','resolution','missing','blocking',true));
    end if;
  end if;

  if v_notification then
    select adapter_key,provider,version,status,required_gates into r
    from private.capability_adapter_registry
    where adapter_type='notification' and status in ('candidate','active')
    order by case status when 'active' then 0 else 1 end, updated_at desc limit 1;
    if found then
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','notification','adapter_key',r.adapter_key,'provider',r.provider,'version',r.version,'adapter_status',r.status,'required_gates',r.required_gates,'resolution','resolved'));
    else
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','notification','resolution','missing','blocking',true,'reason','No certified/candidate notification adapter available'));
    end if;
  end if;

  if v_billing then
    select adapter_key,provider,version,status,required_gates into r
    from private.capability_adapter_registry
    where adapter_type='payment' and status in ('candidate','active')
    order by case status when 'active' then 0 else 1 end, updated_at desc limit 1;
    if found then
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','billing','adapter_key',r.adapter_key,'provider',r.provider,'version',r.version,'adapter_status',r.status,'required_gates',r.required_gates,'resolution','resolved'));
    else
      v_plan := v_plan || jsonb_build_array(jsonb_build_object('module','billing','resolution','missing','blocking',true,'reason','No certified/candidate payment adapter available'));
    end if;
  end if;

  return v_plan;
end;
$$;


ALTER FUNCTION "private"."resolve_capability_adapter_plan"("p_normalized_spec" "jsonb", "p_module_plan" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."resolve_factory_builder"("p_factory_run_id" "uuid") RETURNS "text"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_builder text;
  v_input jsonb;
  v_plan jsonb;
  v_status text;
begin
  select input, plan into v_input, v_plan from public.factory_runs where id=p_factory_run_id;
  if not found then return null; end if;

  v_builder := nullif(v_input->>'builder_key','');

  if v_builder is null then
    v_builder := nullif(v_plan#>>'{builders,0,key}','');
  end if;

  if v_builder is null then
    if exists(select 1 from public.build_steps where factory_run_id=p_factory_run_id and step_key ilike '%mobile-flutter%')
       or coalesce(v_plan::text,'') ilike '%mobile-flutter%' then
      v_builder := 'mobile-flutter-v1';
    elsif exists(select 1 from public.build_steps where factory_run_id=p_factory_run_id and step_key ilike '%gis-web%')
       or (coalesce(v_plan::text,'') ilike '%gis%' and coalesce(v_plan::text,'') ilike '%web%') then
      v_builder := 'gis-web-v1';
    end if;
  end if;

  if v_builder is null then return null; end if;
  select status into v_status from public.builder_registry where builder_key=v_builder;
  if v_status='active' then return v_builder; end if;
  if v_status='experimental'
     and coalesce((v_input->>'allow_experimental_builder')::boolean,false)=true
     and v_builder in ('ai-app-v1','desktop-tauri-v1') then
    return v_builder;
  end if;
  return null;
end;
$$;


ALTER FUNCTION "private"."resolve_factory_builder"("p_factory_run_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."route_builder"("p_builder_type" "text" DEFAULT NULL::"text", "p_target" "text" DEFAULT NULL::"text", "p_required_capabilities" "text"[] DEFAULT '{}'::"text"[]) RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $_$
declare
  v_selected record;
  v_candidates jsonb;
  v_candidate_count integer := 0;
  v_result jsonb;
begin
  if p_builder_type is not null and p_builder_type not in ('web','pwa','mobile','desktop','gis','ai','api') then
    raise exception 'Unsupported builder type: %', p_builder_type;
  end if;

  if exists (
    select 1 from unnest(coalesce(p_required_capabilities,'{}'::text[])) c
    where c !~ '^[a-z0-9_]+$'
  ) then
    raise exception 'Invalid capability key';
  end if;

  with eligible as (
    select
      br.builder_key,
      br.builder_type,
      br.runtime,
      br.targets,
      br.capabilities,
      (
        case when p_builder_type is not null and br.builder_type = p_builder_type then 100 else 0 end
        + case when p_target is not null and p_target = any(br.targets) then 20 else 0 end
        + 10 * (
          select count(*)::int
          from unnest(coalesce(p_required_capabilities,'{}'::text[])) c
          where coalesce((br.capabilities ->> c)::boolean,false)
        )
      ) as score
    from public.builder_registry br
    where br.status = 'active'
      and (p_builder_type is null or br.builder_type = p_builder_type)
      and (p_target is null or p_target = any(br.targets))
      and not exists (
        select 1
        from unnest(coalesce(p_required_capabilities,'{}'::text[])) c
        where not coalesce((br.capabilities ->> c)::boolean,false)
      )
  ), ranked as (
    select *, row_number() over(order by score desc, builder_key asc) as rn
    from eligible
  )
  select
    (select jsonb_agg(jsonb_build_object(
      'builder_key', builder_key,
      'builder_type', builder_type,
      'runtime', runtime,
      'targets', targets,
      'capabilities', capabilities,
      'score', score
    ) order by score desc, builder_key asc) from ranked),
    (select count(*)::int from ranked)
  into v_candidates, v_candidate_count;

  select br.builder_key, br.builder_type, br.runtime, br.targets, br.capabilities
  into v_selected
  from public.builder_registry br
  where br.builder_key = (
    select x->>'builder_key'
    from jsonb_array_elements(coalesce(v_candidates,'[]'::jsonb)) x
    limit 1
  );

  if v_selected.builder_key is null then
    v_result := jsonb_build_object(
      'decision','no_match',
      'selected_builder',null,
      'candidate_count',v_candidate_count,
      'candidates',coalesce(v_candidates,'[]'::jsonb),
      'requested',jsonb_build_object(
        'builder_type',p_builder_type,
        'target',p_target,
        'required_capabilities',coalesce(p_required_capabilities,'{}'::text[])
      )
    );
  else
    v_result := jsonb_build_object(
      'decision','selected',
      'selected_builder',jsonb_build_object(
        'builder_key',v_selected.builder_key,
        'builder_type',v_selected.builder_type,
        'runtime',v_selected.runtime,
        'targets',v_selected.targets,
        'capabilities',v_selected.capabilities
      ),
      'candidate_count',v_candidate_count,
      'candidates',coalesce(v_candidates,'[]'::jsonb),
      'requested',jsonb_build_object(
        'builder_type',p_builder_type,
        'target',p_target,
        'required_capabilities',coalesce(p_required_capabilities,'{}'::text[])
      )
    );
  end if;

  insert into private.builder_route_decisions(
    requested_builder_type,requested_target,required_capabilities,
    selected_builder_key,candidate_count,decision
  ) values (
    p_builder_type,p_target,coalesce(p_required_capabilities,'{}'::text[]),
    v_selected.builder_key,v_candidate_count,v_result
  );

  return v_result;
end;
$_$;


ALTER FUNCTION "private"."route_builder"("p_builder_type" "text", "p_target" "text", "p_required_capabilities" "text"[]) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."seed_factory_additional_sources"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $$
declare
  a public.app_specs%rowtype;
  v_builder text;
  v_title text;
  v_app text;
  v_main text;
  v_extra text;
begin
  if new.run_type <> 'build' or new.target_environment='production' or new.production_locked is distinct from true or new.app_spec_id is null then return new; end if;
  select * into a from public.app_specs where id=new.app_spec_id;
  if not found or a.status <> 'approved' then return new; end if;
  v_builder := coalesce(nullif(new.input->>'builder_key',''), a.spec #>> '{selected_builder,builder_key}', a.spec #>> '{routing,selected_builder,builder_key}');
  v_title := left(regexp_replace(coalesce(a.title,'VL Generated App'),'[^A-Za-z0-9 _-]','','g'),80);

  if v_builder in ('web-react-v1','pwa-react-v1') then
    v_app := 'import React from ''react'';' || E'\n' ||
      'export default function App(){return <main style={{fontFamily:''system-ui'',padding:24,maxWidth:900,margin:''0 auto''}}><h1>' || v_title || '</h1><p>Generated by VL Software Factory</p><section><h2>Status</h2><p>Staging build · production locked</p></section></main>}' || E'\n';
    v_main := 'import React from ''react'';' || E'\n' ||
      'import {createRoot} from ''react-dom/client'';' || E'\n' ||
      'import App from ''./App'';' || E'\n' ||
      'createRoot(document.getElementById(''root'')!).render(<React.StrictMode><App/></React.StrictMode>);' || E'\n';
    insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
    values(new.id,new.project_id,'source','web/src/App.tsx',v_app,encode(extensions.digest(v_app,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','1.1','builder_key',v_builder))
    on conflict(factory_run_id,path) do nothing;
    insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
    values(new.id,new.project_id,'source','web/src/main.tsx',v_main,encode(extensions.digest(v_main,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','1.1','builder_key',v_builder))
    on conflict(factory_run_id,path) do nothing;
    if v_builder='pwa-react-v1' then
      v_extra := jsonb_pretty(jsonb_build_object('name',v_title,'short_name',left(v_title,20),'start_url','/','display','standalone','background_color','#ffffff','theme_color','#111111'));
      insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
      values(new.id,new.project_id,'config','web/public/manifest.webmanifest',v_extra,encode(extensions.digest(v_extra,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','1.1','builder_key',v_builder))
      on conflict(factory_run_id,path) do nothing;
      v_extra := 'const CACHE=''vl-pwa-shell-v1'';' || E'\n' ||
        'const SHELL=[''/'',''/index.html''];' || E'\n' ||
        'self.addEventListener(''install'',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));});' || E'\n' ||
        'self.addEventListener(''activate'',event=>{event.waitUntil(self.clients.claim());});' || E'\n' ||
        'self.addEventListener(''fetch'',event=>{' || E'\n' ||
        '  if(event.request.method!==''GET'') return;' || E'\n' ||
        '  event.respondWith(fetch(event.request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));return response;}).catch(()=>caches.match(event.request).then(hit=>hit||caches.match(''/index.html''))));' || E'\n' ||
        '});' || E'\n';
      insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
      values(new.id,new.project_id,'source','web/public/sw.js',v_extra,encode(extensions.digest(v_extra,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','1.1','builder_key',v_builder,'offline_cache_contract',true))
      on conflict(factory_run_id,path) do nothing;
    end if;
  elsif v_builder='api-service-v1' then
    v_main := 'import "jsr:@supabase/functions-js/edge-runtime.d.ts";' || E'\n' ||
      'Deno.serve(async (req:Request)=>{' || E'\n' ||
      '  if(req.method==="OPTIONS") return new Response(null,{headers:{"access-control-allow-origin":"*","access-control-allow-headers":"authorization, content-type"}});' || E'\n' ||
      '  return new Response(JSON.stringify({ok:true,service:' || to_json(v_title)::text || '}),{headers:{"content-type":"application/json"}});' || E'\n' ||
      '});' || E'\n';
    insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
    values(new.id,new.project_id,'source','api/index.ts',v_main,encode(extensions.digest(v_main,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','1.1','builder_key',v_builder))
    on conflict(factory_run_id,path) do nothing;
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."seed_factory_additional_sources"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."seed_factory_sources"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $_$
declare
  a public.app_specs%rowtype;
  v_builder text;
  v_title text;
  v_main text;
  v_manifest text;
  v_pubspec text;
  v_model text;
  v_store text;
  v_test text;
begin
  if new.run_type <> 'build' or new.target_environment='production' or new.production_locked is distinct from true or new.app_spec_id is null then return new; end if;
  select * into a from public.app_specs where id=new.app_spec_id;
  if not found or a.status <> 'approved' then return new; end if;

  v_builder := coalesce(nullif(new.input->>'builder_key',''), a.spec #>> '{selected_builder,builder_key}', a.spec #>> '{routing,selected_builder,builder_key}');
  v_title := left(regexp_replace(coalesce(a.title,'VL Generated App'),'[^A-Za-z0-9 _-]','','g'),80);

  if v_builder='mobile-flutter-v1' then
    v_pubspec := $yaml$name: vl_generated_app
description: Generated by VL Software Factory.
publish_to: 'none'
version: 0.1.0+1
environment:
  sdk: '>=3.10.0 <4.0.0'
dependencies:
  flutter:
    sdk: flutter
  geolocator: 14.1.1
  shared_preferences: 2.5.5
  maplibre_gl: 0.27.1
dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: 6.0.0
flutter:
  uses-material-design: true
$yaml$;

    v_model := $dart$import 'dart:convert';

class FieldPoint {
  final String id;
  final String label;
  final double latitude;
  final double longitude;
  final double accuracyM;
  final DateTime capturedAt;
  const FieldPoint({required this.id,required this.label,required this.latitude,required this.longitude,required this.accuracyM,required this.capturedAt});
  Map<String,dynamic> toJson()=>{'id':id,'label':label,'latitude':latitude,'longitude':longitude,'accuracy_m':accuracyM,'captured_at':capturedAt.toUtc().toIso8601String()};
  factory FieldPoint.fromJson(Map<String,dynamic> j)=>FieldPoint(id:j['id'] as String,label:(j['label']??'Point') as String,latitude:(j['latitude'] as num).toDouble(),longitude:(j['longitude'] as num).toDouble(),accuracyM:(j['accuracy_m'] as num? ?? 0).toDouble(),capturedAt:DateTime.parse(j['captured_at'] as String));
}
String pointsToJson(List<FieldPoint> pts)=>jsonEncode(pts.map((p)=>p.toJson()).toList());
List<FieldPoint> pointsFromJson(String raw)=>(jsonDecode(raw) as List).map((e)=>FieldPoint.fromJson(Map<String,dynamic>.from(e as Map))).toList();
String pointsToCsv(List<FieldPoint> pts){
  final rows=<String>['label,latitude,longitude,accuracy_m,captured_at'];
  rows.addAll(pts.map((p)=>'${p.label.replaceAll(',', ' ')},${p.latitude},${p.longitude},${p.accuracyM},${p.capturedAt.toUtc().toIso8601String()}'));
  return rows.join('\n');
}
String pointsToKml(List<FieldPoint> pts)=>'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'+pts.map((p)=>'<Placemark><name>${p.label}</name><Point><coordinates>${p.longitude},${p.latitude},0</coordinates></Point></Placemark>').join()+'</Document></kml>';
$dart$;

    v_store := $dart$import 'package:shared_preferences/shared_preferences.dart';
import 'field_point.dart';

class OfflinePointStore {
  static const _key='vl_field_points_v1';
  Future<List<FieldPoint>> load() async {
    final prefs=await SharedPreferences.getInstance();
    final raw=prefs.getString(_key);
    if(raw==null || raw.isEmpty) return <FieldPoint>[];
    return pointsFromJson(raw);
  }
  Future<void> save(List<FieldPoint> pts) async {
    final prefs=await SharedPreferences.getInstance();
    await prefs.setString(_key,pointsToJson(pts));
  }
}
$dart$;

    v_main := format($dart$import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'field_point.dart';
import 'offline_store.dart';

void main()=>runApp(const VLFieldApp());
class VLFieldApp extends StatelessWidget {
  const VLFieldApp({super.key});
  @override Widget build(BuildContext context)=>MaterialApp(debugShowCheckedModeBanner:false,title:%L,theme:ThemeData(useMaterial3:true,colorSchemeSeed:Colors.teal),home:const FieldHome());
}
class FieldHome extends StatefulWidget { const FieldHome({super.key}); @override State<FieldHome> createState()=>_FieldHomeState(); }
class _FieldHomeState extends State<FieldHome> {
  final _store=OfflinePointStore();
  final List<FieldPoint> _points=[];
  bool _busy=false;
  String _status='Ready';
  @override void initState(){super.initState();_restore();}
  Future<void> _restore() async { final p=await _store.load(); if(mounted)setState(()=>_points.addAll(p)); }
  Future<bool> _ensurePermission() async {
    if(!await Geolocator.isLocationServiceEnabled()){setState(()=>_status='Location service disabled');return false;}
    var p=await Geolocator.checkPermission();
    if(p==LocationPermission.denied)p=await Geolocator.requestPermission();
    if(p==LocationPermission.denied || p==LocationPermission.deniedForever){setState(()=>_status='Location permission denied');return false;}
    return true;
  }
  Future<void> _capture() async {
    if(_busy)return; setState(()=>_busy=true);
    try{
      if(!await _ensurePermission())return;
      final pos=await Geolocator.getCurrentPosition(locationSettings:const LocationSettings(accuracy:LocationAccuracy.high,timeLimit:Duration(seconds:20)));
      final p=FieldPoint(id:DateTime.now().microsecondsSinceEpoch.toString(),label:'P${(_points.length+1).toString().padLeft(3,'0')}',latitude:pos.latitude,longitude:pos.longitude,accuracyM:pos.accuracy,capturedAt:DateTime.now().toUtc());
      setState(()=>_points.insert(0,p)); await _store.save(_points); setState(()=>_status='Captured ${p.label} · ±${p.accuracyM.toStringAsFixed(1)} m');
    } catch(e){setState(()=>_status='Capture failed: $e');} finally {if(mounted)setState(()=>_busy=false);}
  }
  Future<void> _copy(String value,String kind) async { await Clipboard.setData(ClipboardData(text:value)); if(mounted)ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text('$kind copied to clipboard'))); }
  @override Widget build(BuildContext context)=>Scaffold(
    appBar:AppBar(title:const Text(%L)),
    body:Column(children:[
      Expanded(flex:3,child:MapLibreMap(styleString:'https://demotiles.maplibre.org/style.json',initialCameraPosition:const CameraPosition(target:LatLng(5.9804,116.0735),zoom:10),myLocationEnabled:true)),
      Padding(padding:const EdgeInsets.fromLTRB(12,8,12,4),child:Row(children:[Expanded(child:Text(_status,maxLines:2)),FilledButton.icon(onPressed:_busy?null:_capture,icon:const Icon(Icons.add_location_alt),label:Text(_busy?'Capturing...':'Capture GPS'))])),
      Padding(padding:const EdgeInsets.symmetric(horizontal:12),child:Row(children:[OutlinedButton(onPressed:_points.isEmpty?null:()=>_copy(pointsToCsv(_points),'CSV'),child:const Text('Export CSV')),const SizedBox(width:8),OutlinedButton(onPressed:_points.isEmpty?null:()=>_copy(pointsToKml(_points),'KML'),child:const Text('Export KML')),const Spacer(),Text('${_points.length} point(s)') ])),
      Expanded(flex:2,child:_points.isEmpty?const Center(child:Text('No captured points yet')):ListView.builder(itemCount:_points.length,itemBuilder:(c,i){final p=_points[i];return ListTile(dense:true,leading:const Icon(Icons.location_on),title:Text(p.label),subtitle:Text('${p.latitude.toStringAsFixed(7)}, ${p.longitude.toStringAsFixed(7)} · ±${p.accuracyM.toStringAsFixed(1)} m'));}))
    ])
  );
}
$dart$,v_title,v_title);

    v_test := $dart$import 'package:flutter_test/flutter_test.dart';
import 'package:vl_generated_app/field_point.dart';
void main(){
  test('field point JSON roundtrip and exports',(){
    final p=FieldPoint(id:'1',label:'P001',latitude:5.9804,longitude:116.0735,accuracyM:2.5,capturedAt:DateTime.utc(2026,8,26));
    final restored=pointsFromJson(pointsToJson([p])).single;
    expect(restored.latitude,p.latitude); expect(restored.longitude,p.longitude);
    expect(pointsToCsv([p]),contains('P001,5.9804,116.0735'));
    expect(pointsToKml([p]),contains('<coordinates>116.0735,5.9804,0</coordinates>'));
  });
}
$dart$;

    insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata) values
      (new.id,new.project_id,'config','mobile/flutter/pubspec.yaml',v_pubspec,encode(extensions.digest(v_pubspec,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder)),
      (new.id,new.project_id,'source','mobile/flutter/lib/field_point.dart',v_model,encode(extensions.digest(v_model,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder)),
      (new.id,new.project_id,'source','mobile/flutter/lib/offline_store.dart',v_store,encode(extensions.digest(v_store,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder)),
      (new.id,new.project_id,'source','mobile/flutter/lib/main.dart',v_main,encode(extensions.digest(v_main,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder)),
      (new.id,new.project_id,'test','mobile/flutter/test/field_point_test.dart',v_test,encode(extensions.digest(v_test,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder))
    on conflict(factory_run_id,path) do nothing;

  elsif v_builder='gis-web-v1' then
    v_main := $ts$import { Map } from 'maplibre-gl';
export function createMap(container:string){return new Map({container,style:'https://demotiles.maplibre.org/style.json',center:[116.0735,5.9804],zoom:10});}
$ts$;
    insert into public.generated_artifacts(factory_run_id,project_id,build_step_id,artifact_kind,path,content,sha256,metadata)
    values(new.id,new.project_id,null,'source','gis/src/map.ts',v_main,encode(extensions.digest(v_main,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder)) on conflict(factory_run_id,path) do nothing;
  end if;

  v_manifest := jsonb_pretty(jsonb_build_object('schema','vrs.factory-source-manifest/2','factory_run_id',new.id,'app_spec_id',new.app_spec_id,'builder_key',v_builder,'target_environment',new.target_environment,'production_locked',new.production_locked,'title',a.title,'objective',a.objective,'spec',a.spec));
  insert into public.generated_artifacts(factory_run_id,project_id,build_step_id,artifact_kind,path,content,sha256,metadata)
  values(new.id,new.project_id,null,'manifest','vrs/factory-source-manifest.json',v_manifest,encode(extensions.digest(v_manifest,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder)) on conflict(factory_run_id,path) do nothing;
  return new;
end;
$_$;


ALTER FUNCTION "private"."seed_factory_sources"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."seed_gis_kml_export_source"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $_$
declare
  a public.app_specs%rowtype;
  v_builder text;
  v_kml text;
begin
  if new.run_type <> 'build' or new.target_environment='production' or new.production_locked is distinct from true or new.app_spec_id is null then return new; end if;
  select * into a from public.app_specs where id=new.app_spec_id;
  if not found or a.status <> 'approved' then return new; end if;
  v_builder := coalesce(nullif(new.input->>'builder_key',''), a.spec #>> '{selected_builder,builder_key}', a.spec #>> '{routing,selected_builder,builder_key}');
  if v_builder <> 'gis-web-v1' then return new; end if;

  v_kml := $ts$export type KmlPoint={name?:string;longitude:number;latitude:number};
export function pointsToKml(points:KmlPoint[]):string{
  const escapeXml=(v:string)=>v.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;');
  const marks=points.map((p,i)=>`<Placemark><name>${escapeXml(p.name??`P${i+1}`)}</name><Point><coordinates>${p.longitude},${p.latitude},0</coordinates></Point></Placemark>`).join('');
  return `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>${marks}</Document></kml>`;
}
export const exportKml=pointsToKml;
$ts$;

  insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
  values(new.id,new.project_id,'source','gis/src/kml.ts',v_kml,encode(extensions.digest(v_kml,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.1','builder_key',v_builder,'kml_export_contract',true))
  on conflict(factory_run_id,path) do nothing;
  return new;
end;
$_$;


ALTER FUNCTION "private"."seed_gis_kml_export_source"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."seed_mobile_android_manifest"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $_$
declare
  a public.app_specs%rowtype;
  v_builder text;
  v_manifest text;
begin
  if new.run_type <> 'build' or new.target_environment='production' or new.production_locked is distinct from true or new.app_spec_id is null then return new; end if;
  select * into a from public.app_specs where id=new.app_spec_id;
  if not found or a.status <> 'approved' then return new; end if;
  v_builder := coalesce(nullif(new.input->>'builder_key',''), a.spec #>> '{selected_builder,builder_key}', a.spec #>> '{routing,selected_builder,builder_key}');
  if v_builder <> 'mobile-flutter-v1' then return new; end if;
  v_manifest := $xml$<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
    <uses-permission android:name="android.permission.INTERNET"/>
    <application android:label="vl_generated_app" android:name="${applicationName}" android:icon="@mipmap/ic_launcher">
        <activity android:name=".MainActivity" android:exported="true" android:launchMode="singleTop" android:taskAffinity="" android:theme="@style/LaunchTheme" android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode" android:hardwareAccelerated="true" android:windowSoftInputMode="adjustResize">
            <meta-data android:name="io.flutter.embedding.android.NormalTheme" android:resource="@style/NormalTheme"/>
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <meta-data android:name="flutterEmbedding" android:value="2"/>
    </application>
    <queries>
        <intent><action android:name="android.intent.action.PROCESS_TEXT"/><data android:mimeType="text/plain"/></intent>
    </queries>
</manifest>
$xml$;
  insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
  values(new.id,new.project_id,'config','mobile/flutter/android/app/src/main/AndroidManifest.xml',v_manifest,encode(extensions.digest(v_manifest,'sha256'),'hex'),jsonb_build_object('auto_seeded',true,'generator_version','2.0','builder_key',v_builder,'gps_permissions',true))
  on conflict(factory_run_id,path) do nothing;
  return new;
end;
$_$;


ALTER FUNCTION "private"."seed_mobile_android_manifest"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."seed_upgrade_source_from_base"("p_upgrade_run_id" "uuid", "p_base_run_id" "uuid", "p_change_request" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $$
declare
  v_upgrade public.factory_runs%rowtype;
  v_base public.factory_runs%rowtype;
  v_base_manifest jsonb := '{}'::jsonb;
  v_manifest jsonb;
  v_change jsonb;
  v_count integer;
begin
  select * into v_upgrade from public.factory_runs where id=p_upgrade_run_id;
  select * into v_base from public.factory_runs where id=p_base_run_id;
  if not found or v_upgrade.id is null or v_base.id is null then raise exception 'upgrade/base run not found'; end if;
  if v_upgrade.run_type<>'upgrade' or v_upgrade.base_factory_run_id is distinct from v_base.id then raise exception 'invalid upgrade lineage'; end if;
  if coalesce(v_base.result->>'runner_status','')<>'PASS' then raise exception 'base run must have runner PASS'; end if;

  select content::jsonb into v_base_manifest
  from public.generated_artifacts
  where factory_run_id=v_base.id and path='vrs/factory-source-manifest.json'
  limit 1;
  v_base_manifest:=coalesce(v_base_manifest,'{}'::jsonb);

  delete from public.generated_artifacts where factory_run_id=v_upgrade.id;

  insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
  select v_upgrade.id,v_upgrade.project_id,ga.artifact_kind,ga.path,ga.content,ga.sha256,
         ga.metadata || jsonb_build_object(
           'upgrade_inherited',true,
           'upgrade_base_factory_run_id',v_base.id,
           'upgrade_base_artifact_sha256',coalesce(v_base.result#>>'{runner,artifact_sha256}','')
         )
  from public.generated_artifacts ga
  where ga.factory_run_id=v_base.id and ga.path<>'vrs/factory-source-manifest.json';
  get diagnostics v_count=row_count;

  v_change:=jsonb_build_object(
    'schema','vrs.upgrade-change-request/1',
    'upgrade_factory_run_id',v_upgrade.id,
    'base_factory_run_id',v_base.id,
    'base_app_spec_id',v_base.app_spec_id,
    'upgrade_app_spec_id',v_upgrade.app_spec_id,
    'change_request',p_change_request,
    'change_application_status','pending'
  );

  insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
  values(v_upgrade.id,v_upgrade.project_id,'manifest','vrs/upgrade-change-request.json',v_change::text,
         encode(digest(convert_to(v_change::text,'UTF8'),'sha256'),'hex'),
         jsonb_build_object('upgrade_contract',true,'change_applied',false));

  v_manifest:=v_base_manifest || jsonb_build_object(
    'revision',jsonb_build_object(
      'kind','upgrade',
      'base_factory_run_id',v_base.id,
      'upgrade_factory_run_id',v_upgrade.id,
      'change_request_manifest','vrs/upgrade-change-request.json',
      'source_inheritance','authoritative_base_copy',
      'change_application_status','pending'
    )
  );

  insert into public.generated_artifacts(factory_run_id,project_id,artifact_kind,path,content,sha256,metadata)
  values(v_upgrade.id,v_upgrade.project_id,'manifest','vrs/factory-source-manifest.json',v_manifest::text,
         encode(digest(convert_to(v_manifest::text,'UTF8'),'sha256'),'hex'),
         jsonb_build_object('upgrade_contract',true,'upgrade_base_factory_run_id',v_base.id,'change_applied',false));

  return jsonb_build_object('decision','upgrade_source_seeded','base_factory_run_id',v_base.id,'upgrade_factory_run_id',v_upgrade.id,'inherited_artifact_count',v_count,'change_application_status','pending');
end;
$$;


ALTER FUNCTION "private"."seed_upgrade_source_from_base"("p_upgrade_run_id" "uuid", "p_base_run_id" "uuid", "p_change_request" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."set_spec_compilation_capability_plan"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  new.capability_adapter_plan := private.resolve_capability_adapter_plan(new.normalized_spec,new.module_plan);
  return new;
end;
$$;


ALTER FUNCTION "private"."set_spec_compilation_capability_plan"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."sync_successful_rollback_rehearsal_gate"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  d public.deployments%rowtype;
  prev public.deployments%rowtype;
begin
  if new.state <> 'succeeded' then return new; end if;
  if coalesce(new.result->>'post_rollback_verification','') <> 'PASS' then return new; end if;
  if coalesce(new.result->>'immutable_no_rebuild','false') <> 'true' then return new; end if;
  if nullif(new.artifact_sha256,'') is null then return new; end if;

  select * into d from public.deployments where id=new.deployment_id;
  select * into prev from public.deployments where id=new.previous_deployment_id;
  if not found then return new; end if;
  if d.factory_run_id is null then return new; end if;
  if lower(coalesce(prev.artifact_sha256,'')) <> lower(new.artifact_sha256) then return new; end if;

  update public.release_gates
     set status='pass',
         score=1.00,
         checked_at=coalesce(new.finished_at,now()),
         evidence=jsonb_build_object(
           'source','production_rollback_audit',
           'rollback_audit_id',new.id,
           'restored_deployment_id',new.previous_deployment_id,
           'artifact_sha256',new.artifact_sha256,
           'immutable_no_rebuild',true,
           'post_rollback_verification','PASS',
           'github_run_id',new.result->>'github_run_id',
           'verification_checks',coalesce(new.result->'verification_checks','[]'::jsonb)
         )
   where factory_run_id=d.factory_run_id
     and gate_key='rollback_rehearsal';
  return new;
end $$;


ALTER FUNCTION "private"."sync_successful_rollback_rehearsal_gate"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."validate_agent_audit_chain"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'pg_catalog', 'private'
    AS $$
declare
  prior_seq integer;
  prior_digest text;
begin
  select event_seq, event_digest
    into prior_seq, prior_digest
  from private.agent_control_audit_events
  where action_id = new.action_id
  order by event_seq desc
  limit 1
  for update;

  if not found then
    if new.event_seq <> 1 or new.previous_event_digest is not null then
      raise exception 'ACP audit chain must start at sequence 1 with no previous digest';
    end if;
  else
    if new.event_seq <> prior_seq + 1 then
      raise exception 'ACP audit sequence is not contiguous';
    end if;
    if new.previous_event_digest is distinct from prior_digest then
      raise exception 'ACP audit previous digest does not match chain head';
    end if;
  end if;
  return new;
end;
$$;


ALTER FUNCTION "private"."validate_agent_audit_chain"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."validate_agent_capability_grant"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'pg_catalog', 'private'
    AS $$
declare
  parent_row private.agent_capability_grants%rowtype;
  current_parent uuid;
  depth integer := 0;
  key text;
begin
  if new.delegated_from_grant_id is null then
    return new;
  end if;

  if new.delegated_from_grant_id = new.grant_id then
    raise exception 'ACP delegation cannot self-reference';
  end if;

  select * into parent_row
  from private.agent_capability_grants
  where grant_id = new.delegated_from_grant_id;

  if not found then
    raise exception 'ACP parent grant missing';
  end if;
  if parent_row.revoked_at is not null then
    raise exception 'ACP parent grant revoked';
  end if;
  if not (new.capabilities <@ parent_row.capabilities) then
    raise exception 'ACP delegated capabilities exceed parent';
  end if;
  if not (parent_row.scope @> new.scope) then
    raise exception 'ACP delegated scope exceeds parent';
  end if;
  if new.valid_from < parent_row.valid_from then
    raise exception 'ACP delegated validity starts before parent';
  end if;
  if parent_row.valid_until is not null and (new.valid_until is null or new.valid_until > parent_row.valid_until) then
    raise exception 'ACP delegated validity exceeds parent';
  end if;

  foreach key in array array['timeout_seconds','max_retries','max_cost_minor'] loop
    if new.budget ? key and parent_row.budget ? key then
      if (new.budget->>key)::numeric > (parent_row.budget->>key)::numeric then
        raise exception 'ACP delegated budget exceeds parent for %', key;
      end if;
    end if;
  end loop;

  current_parent := parent_row.delegated_from_grant_id;
  while current_parent is not null loop
    depth := depth + 1;
    if depth > 16 then
      raise exception 'ACP delegation depth exceeded';
    end if;
    if current_parent = new.grant_id then
      raise exception 'ACP delegation cycle detected';
    end if;
    select delegated_from_grant_id into current_parent
    from private.agent_capability_grants
    where grant_id = current_parent;
    if not found then
      raise exception 'ACP ancestor grant missing';
    end if;
  end loop;

  return new;
end;
$$;


ALTER FUNCTION "private"."validate_agent_capability_grant"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."validate_product_alignment"("p_alignment" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE
    SET "search_path" TO ''
    AS $$
declare
  fi jsonb;
  reqs jsonb;
  tests jsonb;
  manifest jsonb;
  r jsonb;
  t jsonb;
  rid text;
  tid text;
  ref text;
  declared_test text;
begin
  if p_alignment is null or jsonb_typeof(p_alignment) <> 'object' then
    return jsonb_build_object('ok',false,'reason','product_alignment_missing');
  end if;

  fi := p_alignment->'founder_intent';
  reqs := p_alignment->'user_requirements';
  tests := p_alignment->'acceptance_tests';
  manifest := p_alignment->'traceability_manifest';

  if fi is null or jsonb_typeof(fi) <> 'object' then
    return jsonb_build_object('ok',false,'reason','founder_intent_missing');
  end if;

  if nullif(btrim(fi->>'primary_user'),'') is null
     or nullif(btrim(fi->>'core_problem'),'') is null
     or nullif(btrim(fi->>'desired_outcome'),'') is null
     or nullif(btrim(fi->>'success_metric'),'') is null
     or nullif(btrim(fi->>'commercial_model'),'') is null
     or nullif(btrim(fi->>'release_scope'),'') is null then
    return jsonb_build_object('ok',false,'reason','founder_intent_required_text_missing');
  end if;

  if jsonb_typeof(fi->'must_have') <> 'array' or jsonb_array_length(fi->'must_have') = 0
     or jsonb_typeof(fi->'must_not') <> 'array' or jsonb_array_length(fi->'must_not') = 0
     or jsonb_typeof(fi->'compliance_constraints') <> 'array' or jsonb_array_length(fi->'compliance_constraints') = 0
     or jsonb_typeof(fi->'human_decision_boundaries') <> 'array' or jsonb_array_length(fi->'human_decision_boundaries') = 0 then
    return jsonb_build_object('ok',false,'reason','founder_intent_required_array_missing');
  end if;

  if jsonb_typeof(reqs) <> 'array' or jsonb_array_length(reqs)=0 then
    return jsonb_build_object('ok',false,'reason','user_requirements_missing');
  end if;
  if jsonb_typeof(tests) <> 'array' or jsonb_array_length(tests)=0 then
    return jsonb_build_object('ok',false,'reason','acceptance_tests_missing');
  end if;

  if exists (
    select 1
    from jsonb_array_elements(reqs) q
    group by q->>'id'
    having nullif(btrim(q->>'id'),'') is null or count(*) > 1
  ) then
    return jsonb_build_object('ok',false,'reason','requirement_ids_invalid');
  end if;

  if exists (
    select 1
    from jsonb_array_elements(tests) x
    group by x->>'id'
    having nullif(btrim(x->>'id'),'') is null or count(*) > 1
  ) then
    return jsonb_build_object('ok',false,'reason','acceptance_test_ids_invalid');
  end if;

  for r in select value from jsonb_array_elements(reqs) loop
    rid := r->>'id';
    if nullif(btrim(r->>'user'),'') is null
       or nullif(btrim(r->>'context'),'') is null
       or nullif(btrim(r->>'expected_outcome'),'') is null
       or nullif(btrim(r->>'priority'),'') is null
       or jsonb_typeof(r->'intent_refs') <> 'array'
       or jsonb_array_length(r->'intent_refs') = 0 then
      return jsonb_build_object('ok',false,'reason','requirement_fields_missing','requirement_id',rid);
    end if;

    if jsonb_typeof(fi->'intent_ids')='array' then
      for ref in select value #>> '{}' from jsonb_array_elements(r->'intent_refs') loop
        if not (fi->'intent_ids' ? ref) then
          return jsonb_build_object('ok',false,'reason','unknown_founder_intent_ref','requirement_id',rid,'ref',ref);
        end if;
      end loop;
    end if;

    if r->>'priority'='P0' then
      if jsonb_typeof(r->'acceptance_test_ids') <> 'array' or jsonb_array_length(r->'acceptance_test_ids')=0 then
        return jsonb_build_object('ok',false,'reason','p0_acceptance_mapping_missing','requirement_id',rid);
      end if;
      for declared_test in select value #>> '{}' from jsonb_array_elements(r->'acceptance_test_ids') loop
        if not exists (
          select 1 from jsonb_array_elements(tests) x
          where x->>'id'=declared_test
            and jsonb_typeof(x->'requirement_ids')='array'
            and x->'requirement_ids' ? rid
        ) then
          return jsonb_build_object('ok',false,'reason','p0_mapping_not_bidirectional','requirement_id',rid,'test_id',declared_test);
        end if;
      end loop;
    end if;
  end loop;

  for t in select value from jsonb_array_elements(tests) loop
    tid := t->>'id';
    if jsonb_typeof(t->'requirement_ids') <> 'array' or jsonb_array_length(t->'requirement_ids')=0
       or nullif(btrim(t->>'observable_pass_condition'),'') is null then
      return jsonb_build_object('ok',false,'reason','acceptance_test_fields_missing','test_id',tid);
    end if;
    for rid in select value #>> '{}' from jsonb_array_elements(t->'requirement_ids') loop
      if not exists (select 1 from jsonb_array_elements(reqs) q where q->>'id'=rid) then
        return jsonb_build_object('ok',false,'reason','acceptance_test_unknown_requirement','test_id',tid,'requirement_id',rid);
      end if;
    end loop;
  end loop;

  if jsonb_typeof(p_alignment->'contradictions')='array' and exists (
    select 1 from jsonb_array_elements(p_alignment->'contradictions') c
    where coalesce(c->>'status','') <> 'resolved'
  ) then
    return jsonb_build_object('ok',false,'reason','unresolved_contradiction');
  end if;

  if manifest is null or jsonb_typeof(manifest) <> 'object'
     or nullif(btrim(manifest->>'founder_intent_hash'),'') is null
     or nullif(btrim(manifest->>'certification_input_hash'),'') is null then
    return jsonb_build_object('ok',false,'reason','traceability_manifest_incomplete');
  end if;

  return jsonb_build_object('ok',true,'contract_version','vrs.product-alignment/1');
end;
$$;


ALTER FUNCTION "private"."validate_product_alignment"("p_alignment" "jsonb") OWNER TO "postgres";


COMMENT ON FUNCTION "private"."validate_product_alignment"("p_alignment" "jsonb") IS 'Fail-closed DB validator for vrs.product-alignment/1. Mirrors the repository product-alignment contract at the execution boundary.';



CREATE OR REPLACE FUNCTION "private"."vl_get_assisted_build_quote_impl"("p_complexity" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "private"."vl_get_assisted_build_quote_impl"("p_complexity" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "private"."vl_prepare_assisted_build_product_alignment_impl"("p_answers" "jsonb", "p_structured" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "private"."vl_prepare_assisted_build_product_alignment_impl"("p_answers" "jsonb", "p_structured" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."acp_delegate_agent_grant_nonprod"("p_action_id" "text", "p_parent_grant_id" "uuid", "p_agent_id" "text", "p_agent_version" "text", "p_role_name" "text", "p_capabilities" "text"[], "p_scope" "jsonb", "p_budget" "jsonb", "p_valid_from" timestamp with time zone, "p_valid_until" timestamp with time zone, "p_actor_evidence" "jsonb") RETURNS "uuid"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'pg_catalog', 'private', 'extensions'
    AS $$
declare
  v_event_id text;
  v_existing_event_id text;
  v_existing_input_digest text;
  v_existing_grant_id uuid;
  v_grant_id uuid;
  v_created_by text;
  v_input_payload jsonb;
  v_input_digest text;
  v_result_digest text;
begin
  perform private.acp_assert_actor_evidence(p_actor_evidence);

  if p_action_id is null or length(p_action_id) < 16 or length(p_action_id) > 160 then
    raise exception 'ACP action_id invalid';
  end if;
  if p_parent_grant_id is null then
    raise exception 'ACP runtime root grant issuance is prohibited';
  end if;
  if coalesce(p_agent_id, '') = '' or coalesce(p_agent_version, '') = '' or coalesce(p_role_name, '') = '' then
    raise exception 'ACP agent identity incomplete';
  end if;
  if p_capabilities is null or cardinality(p_capabilities) = 0 then
    raise exception 'ACP delegated capabilities required';
  end if;
  if p_capabilities && array['production.approve','production.promote']::text[] then
    raise exception 'ACP production capability cannot be delegated by live boundary';
  end if;
  if jsonb_typeof(p_scope) <> 'object' or p_scope = '{}'::jsonb then
    raise exception 'ACP delegated scope required';
  end if;
  if coalesce(p_scope->>'target_environment', '') not in ('development', 'staging') then
    raise exception 'ACP live delegation is non-production only';
  end if;
  if jsonb_typeof(p_budget) <> 'object' then
    raise exception 'ACP delegated budget must be object';
  end if;
  if p_valid_from is null or p_valid_until is null or p_valid_until <= p_valid_from then
    raise exception 'ACP bounded delegated validity required';
  end if;

  v_input_payload := jsonb_build_object(
    'parent_grant_id', p_parent_grant_id,
    'agent_id', p_agent_id,
    'agent_version', p_agent_version,
    'role_name', p_role_name,
    'capabilities', to_jsonb(p_capabilities),
    'scope', p_scope,
    'budget', p_budget,
    'valid_from', p_valid_from,
    'valid_until', p_valid_until
  );
  v_input_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_input_payload::text, 'UTF8'), 'sha256'), 'hex'
  );

  v_event_id := private.acp_admin_event_id(p_action_id, 'delegation_recorded');
  perform pg_advisory_xact_lock(hashtextextended(p_action_id, 0));

  select event_id, input_digest, nullif(metadata->>'grant_id', '')::uuid
    into v_existing_event_id, v_existing_input_digest, v_existing_grant_id
  from private.agent_control_audit_events
  where action_id = p_action_id
  order by event_seq
  limit 1;

  if found then
    if v_existing_event_id <> v_event_id then
      raise exception 'ACP action_id already consumed by different operation';
    end if;
    if v_existing_input_digest <> v_input_digest then
      raise exception 'ACP replay input digest mismatch';
    end if;
    if v_existing_grant_id is null then
      raise exception 'ACP delegation replay evidence missing grant id';
    end if;
    return v_existing_grant_id;
  end if;

  v_created_by := 'github-oidc:' || (p_actor_evidence->>'actor') || ':' || (p_actor_evidence->>'run_id');
  v_grant_id := gen_random_uuid();

  insert into private.agent_capability_grants (
    grant_id, agent_id, principal_type, agent_version, role_name, capabilities,
    scope, budget, delegated_from_grant_id, valid_from, valid_until, created_by
  ) values (
    v_grant_id, p_agent_id, 'agent', p_agent_version, p_role_name, p_capabilities,
    p_scope, p_budget, p_parent_grant_id, p_valid_from, p_valid_until, v_created_by
  );

  v_result_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_grant_id::text, 'UTF8'), 'sha256'), 'hex'
  );

  perform private.acp_append_admin_audit_event(
    p_action_id,
    'delegation_recorded',
    'acp.delegate_agent_grant',
    p_scope,
    v_input_digest,
    'allow',
    'ALLOW_POLICY_MATCH',
    'succeeded',
    v_result_digest,
    jsonb_build_object('grant_id', v_grant_id, 'parent_grant_id', p_parent_grant_id),
    p_actor_evidence
  );

  return v_grant_id;
end;
$$;


ALTER FUNCTION "public"."acp_delegate_agent_grant_nonprod"("p_action_id" "text", "p_parent_grant_id" "uuid", "p_agent_id" "text", "p_agent_version" "text", "p_role_name" "text", "p_capabilities" "text"[], "p_scope" "jsonb", "p_budget" "jsonb", "p_valid_from" timestamp with time zone, "p_valid_until" timestamp with time zone, "p_actor_evidence" "jsonb") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."acp_delegate_agent_grant_nonprod"("p_action_id" "text", "p_parent_grant_id" "uuid", "p_agent_id" "text", "p_agent_version" "text", "p_role_name" "text", "p_capabilities" "text"[], "p_scope" "jsonb", "p_budget" "jsonb", "p_valid_from" timestamp with time zone, "p_valid_until" timestamp with time zone, "p_actor_evidence" "jsonb") IS 'ACP live write boundary: delegate bounded agent grants for development/staging only; no root grant or production capability issuance.';



CREATE OR REPLACE FUNCTION "public"."acp_read_agent_grant_chain_nonprod"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    SET "search_path" TO ''
    AS $_$
  select private.acp_read_agent_grant_chain_nonprod_impl($1, $2, $3, $4);
$_$;


ALTER FUNCTION "public"."acp_read_agent_grant_chain_nonprod"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."acp_read_agent_grant_chain_nonprod"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") IS 'Security-invoker wrapper for the dedicated server-side LOM non-production grant resolver. EXECUTE restricted to service_role.';



CREATE OR REPLACE FUNCTION "public"."acp_revoke_agent_grant"("p_action_id" "text", "p_grant_id" "uuid", "p_reason" "text", "p_actor_evidence" "jsonb") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'pg_catalog', 'private', 'extensions'
    AS $$
declare
  v_event_id text;
  v_existing_event_id text;
  v_existing_input_digest text;
  v_scope jsonb;
  v_input_payload jsonb;
  v_input_digest text;
  v_result_digest text;
begin
  perform private.acp_assert_actor_evidence(p_actor_evidence);

  if p_action_id is null or length(p_action_id) < 16 or length(p_action_id) > 160 then
    raise exception 'ACP action_id invalid';
  end if;
  if p_grant_id is null or length(trim(coalesce(p_reason, ''))) < 8 or length(p_reason) > 500 then
    raise exception 'ACP revocation requires grant id and bounded reason';
  end if;

  v_input_payload := jsonb_build_object('grant_id', p_grant_id, 'reason', p_reason);
  v_input_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_input_payload::text, 'UTF8'), 'sha256'), 'hex'
  );

  v_event_id := private.acp_admin_event_id(p_action_id, 'policy_decided');
  perform pg_advisory_xact_lock(hashtextextended(p_action_id, 0));

  select event_id, input_digest
    into v_existing_event_id, v_existing_input_digest
  from private.agent_control_audit_events
  where action_id = p_action_id
  order by event_seq
  limit 1;

  if found then
    if v_existing_event_id <> v_event_id then
      raise exception 'ACP action_id already consumed by different operation';
    end if;
    if v_existing_input_digest <> v_input_digest then
      raise exception 'ACP replay input digest mismatch';
    end if;
    return true;
  end if;

  select scope into v_scope
  from private.agent_capability_grants
  where grant_id = p_grant_id
    and principal_type = 'agent'
  for update;

  if not found then
    raise exception 'ACP agent grant not found';
  end if;

  update private.agent_capability_grants
  set revoked_at = coalesce(revoked_at, now()),
      revocation_reason = coalesce(revocation_reason, p_reason)
  where grant_id = p_grant_id
    and principal_type = 'agent';

  v_result_digest := 'sha256:' || encode(
    extensions.digest(convert_to('revoked:' || p_grant_id::text, 'UTF8'), 'sha256'), 'hex'
  );

  perform private.acp_append_admin_audit_event(
    p_action_id,
    'policy_decided',
    'acp.revoke_agent_grant',
    v_scope,
    v_input_digest,
    'allow',
    'ALLOW_POLICY_MATCH',
    'succeeded',
    v_result_digest,
    jsonb_build_object('grant_id', p_grant_id, 'revocation_reason', p_reason),
    p_actor_evidence
  );

  return true;
end;
$$;


ALTER FUNCTION "public"."acp_revoke_agent_grant"("p_action_id" "text", "p_grant_id" "uuid", "p_reason" "text", "p_actor_evidence" "jsonb") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."acp_revoke_agent_grant"("p_action_id" "text", "p_grant_id" "uuid", "p_reason" "text", "p_actor_evidence" "jsonb") IS 'ACP live write boundary: revoke agent grants only; mutation is atomically audit-recorded.';



CREATE OR REPLACE FUNCTION "public"."approve_vrs_notification_production_activation"("p_rationale" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "sql"
    SET "search_path" TO 'public', 'private', 'pg_temp'
    AS $$ select private.approve_notification_production_activation(p_rationale); $$;


ALTER FUNCTION "public"."approve_vrs_notification_production_activation"("p_rationale" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."approve_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  return private.approve_production_release(p_deployment_id,p_rationale);
end
$$;


ALTER FUNCTION "public"."approve_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."bootstrap_reference_saas"("p_template_key" "text" DEFAULT 'contractor_quote_job_tracker'::"text") RETURNS TABLE("organization_id" "uuid", "project_id" "uuid", "app_spec_id" "uuid")
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare
  v_user uuid := auth.uid();
  v_template public.reference_saas_templates%rowtype;
  v_org uuid;
  v_project uuid;
  v_spec uuid;
  v_suffix text;
begin
  if v_user is null then raise exception 'authenticated user required'; end if;
  select * into v_template from public.reference_saas_templates where template_key=p_template_key and status='active';
  if not found then raise exception 'active template not found'; end if;
  v_suffix := substr(replace(v_user::text,'-',''),1,8);

  insert into public.organizations(name,slug,created_by)
  values ('VRS Reference Workspace','vrs-reference-'||v_suffix,v_user)
  on conflict (slug) do update set name=excluded.name
  returning id into v_org;

  insert into public.organization_members(organization_id,user_id,role)
  values (v_org,v_user,'owner')
  on conflict (organization_id,user_id) do update set role='owner';

  insert into public.projects(organization_id,name,slug,description,status,created_by)
  values (v_org,v_template.name,v_template.recommended_slug||'-'||v_suffix,v_template.objective,'active',v_user)
  on conflict (organization_id,slug) do update set description=excluded.description
  returning id into v_project;

  insert into public.project_members(project_id,user_id,role)
  values (v_project,v_user,'owner')
  on conflict (project_id,user_id) do update set role='owner';

  insert into public.app_specs(project_id,version,title,objective,spec,status,created_by,approved_by,approved_at)
  values (v_project,1,v_template.name,v_template.objective,v_template.spec,'approved',v_user,v_user,now())
  on conflict (project_id,version) do update set title=excluded.title,objective=excluded.objective,spec=excluded.spec,status='approved',approved_by=v_user,approved_at=now()
  returning id into v_spec;

  insert into public.environments(project_id,name,kind,status)
  values
    (v_project,'Development','development','ready'),
    (v_project,'Staging','staging','ready'),
    (v_project,'Production','production','paused')
  on conflict (project_id,kind) do nothing;

  return query select v_org,v_project,v_spec;
end;
$$;


ALTER FUNCTION "public"."bootstrap_reference_saas"("p_template_key" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."claim_vrs_experimental_runner_job"("p_runner_identity" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  j private.runner_jobs%rowtype;
  v_lease uuid := gen_random_uuid();
  v_spec jsonb;
  v_artifacts jsonb;
  v_run public.factory_runs%rowtype;
  v_status text;
begin
  select rj.* into j
  from private.runner_jobs rj
  join public.builder_registry br on br.builder_key=rj.builder_key
  where rj.builder_key in ('ai-app-v1','desktop-tauri-v1')
    and br.status='experimental'
    and (rj.state='queued' or (rj.state='leased' and rj.lease_expires_at < now()))
    and rj.attempts < rj.max_attempts
  order by rj.created_at
  for update of rj skip locked
  limit 1;

  if not found then return jsonb_build_object('status','idle'); end if;

  update private.runner_jobs
  set state='leased', attempts=attempts+1, lease_token=v_lease,
      leased_at=now(), lease_expires_at=now()+interval '20 minutes',
      runner_identity=coalesce(p_runner_identity,'{}'::jsonb), updated_at=now()
  where id=j.id returning * into j;

  select * into v_run from public.factory_runs where id=j.factory_run_id;
  select status into v_status from public.builder_registry where builder_key=j.builder_key;
  if v_run.target_environment='production'
     or v_run.production_locked is distinct from true
     or coalesce((v_run.input->>'allow_experimental_builder')::boolean,false) is distinct from true
     or v_status<>'experimental' then
    update private.runner_jobs set state='failed',error_text='experimental execution boundary rejected',finished_at=now(),updated_at=now() where id=j.id;
    return jsonb_build_object('status','rejected','reason','experimental_execution_boundary_rejected');
  end if;

  select jsonb_build_object(
    'id',a.id,'title',a.title,'objective',a.objective,'spec',a.spec,
    'software_kind',a.software_kind,'target_platforms',a.target_platforms,'status',a.status
  ) into v_spec from public.app_specs a where a.id=v_run.app_spec_id;

  select coalesce(jsonb_agg(jsonb_build_object(
    'path',g.path,'content',g.content,'sha256',g.sha256,'artifact_kind',g.artifact_kind,'metadata',g.metadata
  ) order by g.path),'[]'::jsonb)
  into v_artifacts
  from public.generated_artifacts g where g.factory_run_id=j.factory_run_id;

  return jsonb_build_object(
    'status','leased','job_id',j.id,'lease_token',v_lease,'factory_run_id',j.factory_run_id,
    'builder_key',j.builder_key,'attempt',j.attempts,'max_attempts',j.max_attempts,
    'app_spec',v_spec,'generated_artifacts',v_artifacts,
    'target_environment',v_run.target_environment,'production_locked',v_run.production_locked,
    'experimental',true,'network_policy','restricted_by_workflow','credential_policy','no_control_plane_token_during_build'
  );
end;
$$;


ALTER FUNCTION "public"."claim_vrs_experimental_runner_job"("p_runner_identity" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."claim_vrs_operational_alert_job"("p_runner_identity" "jsonb") RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$select private.claim_operational_alert_job(p_runner_identity);$$;


ALTER FUNCTION "public"."claim_vrs_operational_alert_job"("p_runner_identity" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."claim_vrs_production_promotion_job"("p_runner_identity" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
 j private.production_promotion_jobs%rowtype;
 v_dep public.deployments%rowtype;
 v_art public.factory_artifacts%rowtype;
 v_lease uuid:=gen_random_uuid();
 v_adapter_status text;
 v_adapter_configuration jsonb;
 v_required_credentials jsonb;
begin
 select pj.* into j
 from private.production_promotion_jobs pj
 join private.production_adapter_registry ar on ar.adapter_key=pj.target_adapter and ar.status='active' and ar.configured=true
 where (pj.state='queued' or (pj.state='leased' and pj.lease_expires_at<now())) and pj.attempts<pj.max_attempts
 order by pj.created_at for update of pj skip locked limit 1;
 if not found then return jsonb_build_object('status','idle'); end if;

 select * into v_dep from public.deployments where id=j.deployment_id and factory_run_id=j.factory_run_id and project_id=j.project_id;
 if not found then return jsonb_build_object('status','rejected','reason','deployment_factory_run_binding_mismatch'); end if;
 if v_dep.status<>'approved' or v_dep.approved_by is null then return jsonb_build_object('status','rejected','reason','deployment_not_approved'); end if;

 select * into v_art from public.factory_artifacts
 where factory_run_id=j.factory_run_id and artifact_type='bundle' and lower(sha256)=lower(j.artifact_sha256)
 order by created_at desc limit 1;
 if not found then return jsonb_build_object('status','rejected','reason','immutable_source_artifact_not_found'); end if;

 select status,configuration,required_credentials into v_adapter_status,v_adapter_configuration,v_required_credentials
 from private.production_adapter_registry where adapter_key=j.target_adapter;
 if v_adapter_status<>'active' then return jsonb_build_object('status','rejected','reason','adapter_not_active'); end if;

 update private.production_promotion_jobs
 set state='leased',attempts=attempts+1,lease_token=v_lease,leased_at=now(),lease_expires_at=now()+interval '20 minutes',updated_at=now()
 where id=j.id returning * into j;
 update public.deployments set status='deploying',certificate=certificate||jsonb_build_object('promotion_started_at',now(),'promotion_adapter',j.target_adapter)
 where id=j.deployment_id and factory_run_id=j.factory_run_id;

 return jsonb_build_object('status','leased','job_id',j.id,'lease_token',v_lease,'deployment_id',j.deployment_id,'factory_run_id',j.factory_run_id,'builder_key',j.builder_key,'target_adapter',j.target_adapter,'expected_sha256',j.artifact_sha256,'source_artifact_name',v_art.name,'source_storage_path',v_art.storage_path,'source_github_run_id',v_art.metadata->>'github_run_id','attempt',j.attempts,'max_attempts',j.max_attempts,'adapter_configuration',coalesce(v_adapter_configuration,'{}'::jsonb),'required_credentials',coalesce(v_required_credentials,'[]'::jsonb));
end $$;


ALTER FUNCTION "public"."claim_vrs_production_promotion_job"("p_runner_identity" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."claim_vrs_production_rollback_job"("p_runner_identity" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  r private.production_rollback_audits%rowtype;
  cur public.deployments%rowtype;
  prev public.deployments%rowtype;
  art public.factory_artifacts%rowtype;
  v_lease uuid:=gen_random_uuid();
  v_adapter private.production_adapter_registry%rowtype;
begin
  select * into r
  from private.production_rollback_audits
  where (state='pending' or (state='leased' and lease_expires_at<now()))
    and attempts<max_attempts
  order by requested_at
  for update skip locked
  limit 1;
  if not found then return jsonb_build_object('status','idle'); end if;

  select * into cur from public.deployments where id=r.deployment_id for update;
  if not found then
    update private.production_rollback_audits set state='failed',error_text='current deployment not found',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','current_deployment_not_found');
  end if;
  if cur.status not in ('deployed','failed') then
    update private.production_rollback_audits set state='failed',error_text='current deployment not rollback-eligible',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','current_deployment_not_rollback_eligible');
  end if;

  select * into prev from public.deployments where id=r.previous_deployment_id and project_id=cur.project_id;
  if not found or prev.status not in ('deployed','rolled_back') then
    update private.production_rollback_audits set state='failed',error_text='previous deployment invalid',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','previous_deployment_invalid');
  end if;
  if prev.artifact_sha256 is null or lower(prev.artifact_sha256)<>lower(coalesce(r.artifact_sha256,'')) then
    update private.production_rollback_audits set state='failed',error_text='rollback artifact hash binding mismatch',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','rollback_artifact_hash_binding_mismatch');
  end if;

  select * into art from public.factory_artifacts
  where factory_run_id=prev.factory_run_id and artifact_type='bundle' and lower(sha256)=lower(prev.artifact_sha256)
  order by created_at desc limit 1;
  if not found then
    update private.production_rollback_audits set state='failed',error_text='immutable rollback artifact not found',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','immutable_rollback_artifact_not_found');
  end if;
  if art.storage_path not like 'github-actions://lundus88/fieldgis-reference/runs/%/artifacts/%' then
    update private.production_rollback_audits set state='failed',error_text='trusted GitHub rollback artifact path required',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','trusted_github_artifact_required');
  end if;
  if nullif(art.metadata->>'github_artifact_expires_at','') is null or (art.metadata->>'github_artifact_expires_at')::timestamptz<=now() then
    update private.production_rollback_audits set state='failed',error_text='rollback artifact expired or missing expiry provenance',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','rollback_artifact_expired');
  end if;

  select * into v_adapter from private.production_adapter_registry where adapter_key=r.target_adapter;
  if not found or v_adapter.status<>'active' or v_adapter.configured is distinct from true or v_adapter.can_rollback is distinct from true then
    update private.production_rollback_audits set state='failed',error_text='rollback adapter unavailable',finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','rejected','reason','rollback_adapter_unavailable');
  end if;

  update private.production_rollback_audits
  set state='leased',attempts=attempts+1,lease_token=v_lease,leased_at=now(),lease_expires_at=now()+interval '20 minutes',updated_at=now(),
      evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object('runner_identity',coalesce(p_runner_identity,'{}'::jsonb),'leased_at',now())
  where id=r.id returning * into r;

  return jsonb_build_object(
    'status','leased','rollback_audit_id',r.id,'lease_token',v_lease,'deployment_id',cur.id,'previous_deployment_id',prev.id,
    'target_adapter',r.target_adapter,'expected_sha256',prev.artifact_sha256,'source_artifact_name',art.name,
    'source_storage_path',art.storage_path,'source_github_run_id',art.metadata->>'github_run_id','source_github_artifact_id',art.metadata->>'github_artifact_id',
    'source_commit_sha',prev.source_commit_sha,'attempt',r.attempts,'max_attempts',r.max_attempts,
    'adapter_configuration',coalesce(v_adapter.configuration,'{}'::jsonb),'required_credentials',coalesce(v_adapter.required_credentials,'[]'::jsonb));
end
$$;


ALTER FUNCTION "public"."claim_vrs_production_rollback_job"("p_runner_identity" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."claim_vrs_release_validation_job"("p_runner_identity" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  j private.release_validation_jobs%rowtype; v_lease uuid:=gen_random_uuid(); v_run public.factory_runs%rowtype; v_dep public.deployments%rowtype; v_required jsonb; v_artifacts jsonb;
begin
  select * into j from private.release_validation_jobs where (state='queued' or (state='leased' and lease_expires_at<now())) and attempts<max_attempts order by created_at for update skip locked limit 1;
  if not found then return jsonb_build_object('status','idle'); end if;
  update private.release_validation_jobs set state='leased',attempts=attempts+1,lease_token=v_lease,leased_at=now(),lease_expires_at=now()+interval '20 minutes',runner_identity=coalesce(p_runner_identity,'{}'::jsonb),updated_at=now() where id=j.id returning * into j;
  select * into v_run from public.factory_runs where id=j.factory_run_id;
  select * into v_dep from public.deployments where id=j.deployment_id;
  if v_dep.factory_run_id is distinct from j.factory_run_id or v_dep.status<>'planned' or v_run.state<>'validating' or v_run.production_locked is distinct from true then
    update private.release_validation_jobs set state='failed',error_text='release candidate not eligible',finished_at=now(),updated_at=now() where id=j.id;
    return jsonb_build_object('status','rejected','reason','release_candidate_not_eligible');
  end if;
  v_required:=private.get_deployment_required_gates(v_dep.id);
  if jsonb_array_length(v_required)=0 then raise exception 'deployment gate snapshot missing'; end if;
  select coalesce(jsonb_agg(jsonb_build_object('path',g.path,'content',g.content,'sha256',g.sha256,'artifact_kind',g.artifact_kind,'metadata',g.metadata) order by g.path),'[]'::jsonb) into v_artifacts from public.generated_artifacts g where g.factory_run_id=v_run.id;
  return jsonb_build_object('status','leased','job_id',j.id,'lease_token',v_lease,'deployment_id',j.deployment_id,'factory_run_id',j.factory_run_id,'builder_key',v_dep.builder_key_snapshot,'builder_version',v_dep.builder_version_snapshot,'artifact_sha256',v_dep.artifact_sha256,'required_gates',v_required,'gate_policy_version',v_dep.gate_policy_version_snapshot,'gate_policy_sha256',v_dep.gate_policy_sha256,'generated_artifacts',v_artifacts,'attempt',j.attempts,'max_attempts',j.max_attempts);
end
$$;


ALTER FUNCTION "public"."claim_vrs_release_validation_job"("p_runner_identity" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."claim_vrs_runner_job"("p_runner_identity" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  j private.runner_jobs%rowtype;
  v_lease uuid := gen_random_uuid();
  v_spec jsonb;
  v_artifacts jsonb;
  v_run public.factory_runs%rowtype;
  v_alignment_result jsonb;
begin
  select * into j
  from private.runner_jobs
  where (state='queued' or (state='leased' and lease_expires_at < now()))
    and attempts < max_attempts
  order by created_at
  for update skip locked
  limit 1;

  if not found then return jsonb_build_object('status','idle'); end if;

  update private.runner_jobs
  set state='leased', attempts=attempts+1, lease_token=v_lease,
      leased_at=now(), lease_expires_at=now()+interval '20 minutes',
      runner_identity=coalesce(p_runner_identity,'{}'::jsonb), updated_at=now()
  where id=j.id
  returning * into j;

  select * into v_run from public.factory_runs where id=j.factory_run_id;
  if v_run.target_environment='production' or v_run.production_locked is distinct from true then
    update private.runner_jobs set state='failed', error_text='production execution forbidden', finished_at=now(), updated_at=now() where id=j.id;
    return jsonb_build_object('status','rejected','reason','production_execution_forbidden');
  end if;

  select jsonb_build_object(
    'id',a.id,'title',a.title,'objective',a.objective,'spec',a.spec,
    'software_kind',a.software_kind,'target_platforms',a.target_platforms,'status',a.status
  ) into v_spec from public.app_specs a where a.id=v_run.app_spec_id;

  if coalesce((v_run.input->>'product_alignment_enforced')::boolean,false)
     or private.requires_product_alignment(v_run.app_spec_id) then
    v_alignment_result := private.validate_product_alignment(v_spec#>'{spec,product_alignment}');
    if coalesce((v_alignment_result->>'ok')::boolean,false) is distinct from true then
      update private.runner_jobs
      set state='failed', error_text='product alignment rejected: '||coalesce(v_alignment_result->>'reason','invalid_product_alignment'),
          finished_at=now(), updated_at=now()
      where id=j.id;
      update public.factory_runs
      set state='failed', error_text='product alignment gate rejected runner claim', finished_at=now()
      where id=j.factory_run_id;
      return jsonb_build_object('status','rejected','reason','product_alignment_rejected','detail',v_alignment_result);
    end if;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'path',g.path,'content',g.content,'sha256',g.sha256,'artifact_kind',g.artifact_kind,'metadata',g.metadata
  ) order by g.path),'[]'::jsonb)
  into v_artifacts
  from public.generated_artifacts g where g.factory_run_id=j.factory_run_id;

  return jsonb_build_object(
    'status','leased','job_id',j.id,'lease_token',v_lease,'factory_run_id',j.factory_run_id,
    'builder_key',j.builder_key,'attempt',j.attempts,'max_attempts',j.max_attempts,
    'app_spec',v_spec,'generated_artifacts',v_artifacts,
    'target_environment',v_run.target_environment,'production_locked',v_run.production_locked,
    'product_alignment_enforced',coalesce((v_run.input->>'product_alignment_enforced')::boolean,false)
  );
end;
$$;


ALTER FUNCTION "public"."claim_vrs_runner_job"("p_runner_identity" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."complete_vrs_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text" DEFAULT NULL::"text", "p_error_text" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$select private.complete_operational_alert_job(p_incident_id,p_lease_token,p_success,p_provider_message_id,p_error_text);$$;


ALTER FUNCTION "public"."complete_vrs_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text", "p_error_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."complete_vrs_production_promotion_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb" DEFAULT '{}'::"jsonb", "p_error_text" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare j private.production_promotion_jobs%rowtype; v_dep public.deployments%rowtype; v_sha text; v_checks jsonb; v_bad int;
begin
 select * into j from private.production_promotion_jobs where id=p_job_id for update;
 if not found then raise exception 'promotion job not found'; end if;
 if j.state<>'leased' or j.lease_token is distinct from p_lease_token then raise exception 'invalid promotion lease'; end if;
 if j.lease_expires_at<now() then raise exception 'promotion lease expired'; end if;
 select * into v_dep from public.deployments where id=j.deployment_id for update;
 if p_success then
   v_sha:=nullif(p_result->>'artifact_sha256','');
   if v_sha is null or lower(v_sha)<>lower(j.artifact_sha256) then raise exception 'promoted artifact SHA-256 mismatch'; end if;
   if p_result->>'post_deploy_verification'<>'PASS' then raise exception 'post-deploy verification PASS evidence required'; end if;
   if j.target_adapter<>'mobile-release-artifact' and nullif(p_result->>'provider_url','') is null then raise exception 'provider deployment reference required'; end if;
   v_checks:=coalesce(p_result->'verification_checks','[]'::jsonb);
   if jsonb_typeof(v_checks)<>'array' then raise exception 'verification_checks must be an array'; end if;
   if jsonb_array_length(v_checks)=0 then raise exception 'post-deploy verification checks required'; end if;
   select count(*) into v_bad from jsonb_array_elements(v_checks) c where lower(coalesce(c->>'status',''))<>'pass';
   if v_bad>0 then raise exception 'one or more post-deploy checks failed'; end if;
   insert into private.production_deployment_verifications(deployment_id,promotion_job_id,check_key,expected,actual,status,evidence,checked_at)
   select j.deployment_id,j.id,c->>'check_key',coalesce(c->'expected','null'),coalesce(c->'actual','null'),'pass',coalesce(c->'evidence','{}'),coalesce((c->>'timestamp')::timestamptz,now())
   from jsonb_array_elements(v_checks) c where nullif(c->>'check_key','') is not null
   on conflict(promotion_job_id,check_key) do update set expected=excluded.expected,actual=excluded.actual,status=excluded.status,evidence=excluded.evidence,checked_at=excluded.checked_at;
   update private.production_promotion_jobs set state='succeeded',result=coalesce(p_result,'{}'),error_text=null,finished_at=now(),updated_at=now() where id=j.id;
   update public.deployments set status='deployed',certificate=certificate||jsonb_build_object(
     'promotion','PASS','promotion_adapter',j.target_adapter,'promoted_artifact_sha256',v_sha,
     'provider_deployment_id',coalesce(p_result->>'provider_deployment_id',p_result->>'provider_url'),
     'provider_url',p_result->>'provider_url','post_deploy_verification','PASS',
     'promotion_result',coalesce(p_result,'{}'),'immutable_no_rebuild',true) where id=j.deployment_id;
   return jsonb_build_object('status','recorded','decision','promotion_succeeded','deployment_status','deployed','artifact_sha256',v_sha);
 else
   if j.attempts<j.max_attempts then
     update private.production_promotion_jobs set state='queued',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'),error_text=p_error_text,updated_at=now() where id=j.id;
     update public.deployments set status='approved',certificate=certificate||jsonb_build_object('promotion_retry',true,'last_error',p_error_text) where id=j.deployment_id;
     return jsonb_build_object('status','recorded','decision','retry_queued');
   end if;
   update private.production_promotion_jobs set state='failed',result=coalesce(p_result,'{}'),error_text=p_error_text,finished_at=now(),updated_at=now() where id=j.id;
   update public.deployments set status='failed',certificate=certificate||jsonb_build_object('promotion','FAIL','error',p_error_text,'rollback_state','pending') where id=j.deployment_id;
   return jsonb_build_object('status','recorded','decision','promotion_failed','rollback_state','pending');
 end if;
end $$;


ALTER FUNCTION "public"."complete_vrs_production_promotion_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."complete_vrs_production_rollback_job"("p_rollback_audit_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb" DEFAULT '{}'::"jsonb", "p_error_text" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  r private.production_rollback_audits%rowtype;
  cur public.deployments%rowtype;
  prev public.deployments%rowtype;
  v_sha text;
  v_checks jsonb;
  v_bad int;
begin
  select * into r from private.production_rollback_audits where id=p_rollback_audit_id for update;
  if not found then raise exception 'rollback audit not found'; end if;
  if r.state<>'leased' or r.lease_token is distinct from p_lease_token then raise exception 'invalid rollback lease'; end if;
  if r.lease_expires_at<now() then raise exception 'rollback lease expired'; end if;
  select * into cur from public.deployments where id=r.deployment_id for update;
  select * into prev from public.deployments where id=r.previous_deployment_id;
  if not found then raise exception 'rollback target deployment missing'; end if;

  if p_success then
    v_sha:=nullif(p_result->>'artifact_sha256','');
    if v_sha is null or lower(v_sha)<>lower(coalesce(r.artifact_sha256,'')) then raise exception 'rolled-back artifact SHA-256 mismatch'; end if;
    if p_result->>'post_rollback_verification'<>'PASS' then raise exception 'post-rollback verification PASS evidence required'; end if;
    if r.target_adapter<>'mobile-release-artifact' and nullif(p_result->>'provider_url','') is null then raise exception 'rollback provider reference required'; end if;
    v_checks:=coalesce(p_result->'verification_checks','[]'::jsonb);
    if jsonb_typeof(v_checks)<>'array' or jsonb_array_length(v_checks)=0 then raise exception 'post-rollback verification checks required'; end if;
    select count(*) into v_bad from jsonb_array_elements(v_checks) c where lower(coalesce(c->>'status',''))<>'pass';
    if v_bad>0 then raise exception 'one or more post-rollback checks failed'; end if;

    update private.production_rollback_audits
      set state='succeeded',result=coalesce(p_result,'{}'::jsonb),error_text=null,finished_at=now(),updated_at=now(),
          evidence=coalesce(evidence,'{}'::jsonb)||jsonb_build_object('execution','PASS','post_rollback_verification','PASS','completed_at',now(),'verification_checks',v_checks)
      where id=r.id;

    update public.deployments
      set status='rolled_back',certificate=coalesce(certificate,'{}'::jsonb)||jsonb_build_object(
        'rollback','PASS','rollback_audit_id',r.id,'rollback_target_deployment_id',prev.id,
        'rollback_artifact_sha256',v_sha,'rollback_provider_url',p_result->>'provider_url',
        'post_rollback_verification','PASS','rolled_back_at',now(),'immutable_no_rebuild',true)
      where id=cur.id;

    update public.deployments
      set certificate=coalesce(certificate,'{}'::jsonb)||jsonb_build_object('restored_by_rollback',true,'rollback_audit_id',r.id,'restored_at',now())
      where id=prev.id;

    return jsonb_build_object('status','recorded','decision','rollback_succeeded','deployment_status','rolled_back','restored_deployment_id',prev.id,'artifact_sha256',v_sha);
  else
    if r.attempts<r.max_attempts then
      update private.production_rollback_audits set state='pending',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,updated_at=now() where id=r.id;
      return jsonb_build_object('status','recorded','decision','rollback_retry_queued');
    end if;
    update private.production_rollback_audits set state='failed',result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,finished_at=now(),updated_at=now() where id=r.id;
    return jsonb_build_object('status','recorded','decision','rollback_failed');
  end if;
end
$$;


ALTER FUNCTION "public"."complete_vrs_production_rollback_job"("p_rollback_audit_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."complete_vrs_release_validation_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_gate_results" "jsonb" DEFAULT '[]'::"jsonb", "p_result" "jsonb" DEFAULT '{}'::"jsonb", "p_error_text" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  j private.release_validation_jobs%rowtype; v_dep public.deployments%rowtype; v_required jsonb; r jsonb; v_missing int; v_fail int;
begin
  select * into j from private.release_validation_jobs where id=p_job_id for update;
  if not found then raise exception 'release validation job not found'; end if;
  if j.state<>'leased' or j.lease_token is distinct from p_lease_token then raise exception 'invalid release validation lease'; end if;
  if j.lease_expires_at<now() then raise exception 'release validation lease expired'; end if;
  select * into v_dep from public.deployments where id=j.deployment_id for update;
  if not found or v_dep.factory_run_id is distinct from j.factory_run_id then raise exception 'release validation deployment binding mismatch'; end if;
  v_required:=private.get_deployment_required_gates(j.deployment_id);
  if jsonb_array_length(v_required)=0 then raise exception 'deployment gate snapshot missing'; end if;

  if p_success then
    if jsonb_typeof(coalesce(p_gate_results,'[]'::jsonb))<>'array' then raise exception 'gate_results must be array'; end if;
    for r in select value from jsonb_array_elements(coalesce(p_gate_results,'[]'::jsonb)) loop
      if (r->>'key') in ('human_production_approval','production_lock') then raise exception 'human/production lock gates cannot be set by automated validator'; end if;
      if not exists(select 1 from jsonb_array_elements(v_required) g where g->>'key'=r->>'key') then raise exception 'validator returned gate not present in frozen deployment policy: %',r->>'key'; end if;
      if coalesce(r->>'status','') not in ('pass','fail') then raise exception 'automated gate status must be pass or fail'; end if;
      update public.release_gates set status=r->>'status',score=case when r ? 'score' then (r->>'score')::numeric else case when r->>'status'='pass' then 1 else 0 end end,evidence=coalesce(r->'evidence','{}'::jsonb),checked_at=now(),checked_by=null where factory_run_id=j.factory_run_id and gate_key=r->>'key';
    end loop;
    select count(*) into v_missing from jsonb_array_elements(v_required) g where not exists(select 1 from public.release_gates rg where rg.factory_run_id=j.factory_run_id and rg.gate_key=g->>'key' and rg.status='pass');
    select count(*) into v_fail from jsonb_array_elements(v_required) g where exists(select 1 from public.release_gates rg where rg.factory_run_id=j.factory_run_id and rg.gate_key=g->>'key' and rg.status='fail');
    if v_fail>0 then
      update private.release_validation_jobs set state='failed',result=coalesce(p_result,'{}'::jsonb),error_text='one or more technical release gates failed',finished_at=now(),updated_at=now() where id=j.id;
      update public.deployments set status='failed',certificate=certificate||jsonb_build_object('technical_validation','FAIL','validation_result',coalesce(p_result,'{}'::jsonb)) where id=j.deployment_id;
      update public.factory_runs set state='failed',error_text='Technical release validation failed',finished_at=now() where id=j.factory_run_id;
      update public.workflows w set state='failed',finished_at=now(),output=coalesce(w.output,'{}'::jsonb)||jsonb_build_object('technical_validation','FAIL') from public.factory_runs fr where fr.id=j.factory_run_id and w.id=fr.workflow_id;
      return jsonb_build_object('status','recorded','decision','technical_gates_failed','missing_or_failed',v_missing);
    elsif v_missing=0 then
      update private.release_validation_jobs set state='succeeded',result=coalesce(p_result,'{}'::jsonb),error_text=null,finished_at=now(),updated_at=now() where id=j.id;
      update public.deployments set status='certified',certificate=certificate||jsonb_build_object('technical_validation','PASS','validation_result',coalesce(p_result,'{}'::jsonb),'certified_at',now(),'gate_policy_version',gate_policy_version_snapshot,'gate_policy_sha256',gate_policy_sha256) where id=j.deployment_id;
      update public.factory_runs set state='awaiting_approval',result=coalesce(result,'{}'::jsonb)||jsonb_build_object('technical_certification','PASS'),error_text=null where id=j.factory_run_id and target_environment<>'production' and production_locked=true;
      update public.workflows w set state='waiting_approval',output=coalesce(w.output,'{}'::jsonb)||jsonb_build_object('technical_validation','PASS') from public.factory_runs fr where fr.id=j.factory_run_id and w.id=fr.workflow_id;
      return jsonb_build_object('status','recorded','decision','technically_certified','deployment_status','certified','factory_run_state','awaiting_approval','gate_policy_version',v_dep.gate_policy_version_snapshot,'gate_policy_sha256',v_dep.gate_policy_sha256);
    elsif j.attempts >= j.max_attempts then
      -- Use the existing terminal-failure path. Never certify missing evidence.
      return public.complete_vrs_release_validation_job(
        p_job_id, p_lease_token, false, '[]'::jsonb,
        coalesce(p_result,'{}'::jsonb) || jsonb_build_object('missing_gate_count',v_missing,'retry_exhausted',true),
        'Release validation attempts exhausted with required frozen gates still pending'
      );
    else
      update private.release_validation_jobs set state='queued',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'::jsonb),error_text='required frozen gates still pending',updated_at=now() where id=j.id;
      update public.factory_runs set state='validating',error_text=null where id=j.factory_run_id and state<>'failed';
      return jsonb_build_object('status','recorded','decision','more_validation_required','missing_or_failed',v_missing,'factory_run_state','validating');
    end if;
  else
    if j.attempts<j.max_attempts then
      update private.release_validation_jobs set state='queued',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,updated_at=now() where id=j.id;
      update public.factory_runs set state='validating',error_text=p_error_text where id=j.factory_run_id and state<>'failed';
      return jsonb_build_object('status','recorded','decision','retry_queued','factory_run_state','validating');
    else
      update private.release_validation_jobs set state='failed',result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,finished_at=now(),updated_at=now() where id=j.id;
      update public.deployments set status='failed',certificate=certificate||jsonb_build_object('technical_validation','FAIL','error',p_error_text) where id=j.deployment_id;
      update public.factory_runs set state='failed',error_text=coalesce(p_error_text,'Release validation failed'),finished_at=now() where id=j.factory_run_id;
      update public.workflows w set state='failed',finished_at=now(),output=coalesce(w.output,'{}'::jsonb)||jsonb_build_object('technical_validation','FAIL','error',p_error_text) from public.factory_runs fr where fr.id=j.factory_run_id and w.id=fr.workflow_id;
      return jsonb_build_object('status','recorded','decision','validation_failed','factory_run_state','failed');
    end if;
  end if;
end
$$;


ALTER FUNCTION "public"."complete_vrs_release_validation_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_gate_results" "jsonb", "p_result" "jsonb", "p_error_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."complete_vrs_runner_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb" DEFAULT '{}'::"jsonb", "p_error_text" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  j private.runner_jobs%rowtype;
  v_run_state text;
  v_artifact_name text;
  v_storage_path text;
  v_sha text;
begin
  select * into j from private.runner_jobs where id=p_job_id for update;
  if not found then raise exception 'runner job not found'; end if;
  if j.state <> 'leased' or j.lease_token is distinct from p_lease_token then raise exception 'invalid runner lease'; end if;
  if j.lease_expires_at < now() then raise exception 'runner lease expired'; end if;

  if p_success then
    update private.runner_jobs
      set state='succeeded',result=coalesce(p_result,'{}'::jsonb),error_text=null,finished_at=now(),updated_at=now()
      where id=j.id;

    v_artifact_name := coalesce(nullif(p_result->>'artifact_name',''), j.builder_key || '-build');
    v_sha := nullif(p_result->>'artifact_sha256','');
    v_storage_path := case when nullif(p_result->>'github_run_id','') is not null
      then 'github-actions://lundus88/fieldgis-reference/runs/' || (p_result->>'github_run_id') || '/artifacts/' || v_artifact_name
      else null end;

    insert into public.factory_artifacts(factory_run_id,project_id,artifact_type,name,storage_path,sha256,metadata)
    values(j.factory_run_id,j.project_id,'bundle',v_artifact_name,v_storage_path,v_sha,
      jsonb_build_object('runner','github-actions-oidc','builder_key',j.builder_key,'qa_result','PASS','github_run_id',p_result->>'github_run_id'))
    on conflict(factory_run_id,name) do update
      set storage_path=excluded.storage_path,sha256=excluded.sha256,metadata=excluded.metadata;

    update public.factory_runs
      set state='validating',
          started_at=coalesce(started_at,j.leased_at,j.created_at),
          result=coalesce(result,'{}'::jsonb)||jsonb_build_object('runner',coalesce(p_result,'{}'::jsonb),'runner_status','PASS'),
          error_text=null
      where id=j.factory_run_id and target_environment<>'production' and production_locked=true;

    update public.workflows w
      set state='running',
          started_at=coalesce(w.started_at,j.leased_at,j.created_at),
          output=coalesce(output,'{}'::jsonb)||jsonb_build_object('runner_status','PASS','runner',coalesce(p_result,'{}'::jsonb))
      from public.factory_runs r where r.id=j.factory_run_id and w.id=r.workflow_id;
    v_run_state := 'validating';
  else
    if j.attempts < j.max_attempts then
      update private.runner_jobs
        set state='queued',lease_token=null,leased_at=null,lease_expires_at=null,result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,updated_at=now()
        where id=j.id;
      update public.factory_runs set state='building',started_at=coalesce(started_at,j.leased_at,j.created_at),error_text=p_error_text where id=j.factory_run_id and target_environment<>'production' and production_locked=true;
      v_run_state := 'building';
    else
      update private.runner_jobs set state='failed',result=coalesce(p_result,'{}'::jsonb),error_text=p_error_text,finished_at=now(),updated_at=now() where id=j.id;
      update public.factory_runs set state='failed',started_at=coalesce(started_at,j.leased_at,j.created_at),error_text=p_error_text,finished_at=now() where id=j.factory_run_id;
      update public.workflows w set state='failed',started_at=coalesce(w.started_at,j.leased_at,j.created_at),finished_at=now(),output=coalesce(output,'{}'::jsonb)||jsonb_build_object('runner_status','FAIL','error',p_error_text)
        from public.factory_runs r where r.id=j.factory_run_id and w.id=r.workflow_id;
      v_run_state := 'failed';
    end if;
  end if;

  return jsonb_build_object('status','recorded','job_id',j.id,'factory_run_id',j.factory_run_id,'factory_run_state',v_run_state);
end;
$$;


ALTER FUNCTION "public"."complete_vrs_runner_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."create_organization_with_owner"("p_name" "text", "p_slug" "text") RETURNS "uuid"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare v_id uuid;
begin
  if auth.uid() is null then raise exception 'authentication required'; end if;
  insert into public.organizations(name,slug,created_by)
  values (p_name,p_slug,auth.uid()) returning id into v_id;
  insert into public.organization_members(organization_id,user_id,role)
  values (v_id,auth.uid(),'owner');
  return v_id;
end;
$$;


ALTER FUNCTION "public"."create_organization_with_owner"("p_name" "text", "p_slug" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."create_project_with_owner"("p_organization_id" "uuid", "p_name" "text", "p_slug" "text", "p_description" "text" DEFAULT NULL::"text") RETURNS "uuid"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public', 'private'
    AS $$
declare v_id uuid;
begin
  if auth.uid() is null then raise exception 'authentication required'; end if;
  if not private.has_org_role(p_organization_id,array['owner','admin','builder']) then raise exception 'insufficient organization role'; end if;
  insert into public.projects(organization_id,name,slug,description,created_by)
  values (p_organization_id,p_name,p_slug,p_description,auth.uid()) returning id into v_id;
  insert into public.project_members(project_id,user_id,role)
  values (v_id,auth.uid(),'owner');
  insert into public.environments(project_id,name,kind) values
    (v_id,'development','development'),
    (v_id,'staging','staging'),
    (v_id,'production','production');
  return v_id;
end;
$$;


ALTER FUNCTION "public"."create_project_with_owner"("p_organization_id" "uuid", "p_name" "text", "p_slug" "text", "p_description" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."enqueue_vrs_golden_certification_runs"("p_builder_key" "text", "p_run_count" integer DEFAULT 1) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare v_profile private.builder_certification_golden_profiles%rowtype; v_spec public.app_specs%rowtype; v_project public.projects%rowtype; v_builder public.builder_registry%rowtype; v_workflow_id uuid; v_run_id uuid; v_ids jsonb:='[]'::jsonb; v_actor uuid; i integer;
begin
 if current_user not in ('service_role','postgres') then raise exception 'service-role certification authority required'; end if;
 select * into v_profile from private.builder_certification_golden_profiles where builder_key=p_builder_key and enabled=true; if not found then raise exception 'builder is not whitelisted for golden certification'; end if;
 if p_run_count is null or p_run_count<1 or p_run_count>v_profile.max_batch_runs then raise exception 'run_count outside locked certification batch limit'; end if;
 select * into v_builder from public.builder_registry where builder_key=p_builder_key and status='active'; if not found then raise exception 'only active builders may use golden certification rerun authority'; end if;
 select p.* into v_project from public.projects p where p.name=v_profile.project_name order by p.created_at desc limit 1; if not found then raise exception 'whitelisted golden project not found'; end if;
 select a.* into v_spec from public.app_specs a where a.project_id=v_project.id and a.status='approved' and (v_profile.app_spec_title is null or a.title=v_profile.app_spec_title) and (p_builder_key='mobile-flutter-v1' or coalesce(a.spec #>> '{selected_builder,builder_key}',a.spec #>> '{routing,selected_builder,builder_key}')=p_builder_key) order by a.approved_at desc nulls last,a.created_at desc limit 1;
 if not found then raise exception 'approved whitelisted golden app spec not found'; end if;
 v_actor:=coalesce(v_spec.approved_by,v_spec.created_by); if v_actor is null then raise exception 'golden spec has no accountable actor'; end if;
 if not exists(select 1 from public.project_members pm where pm.project_id=v_project.id and pm.user_id=v_actor and pm.role in ('owner','admin','builder')) then raise exception 'golden spec actor is not an authorized project member'; end if;
 if not exists(select 1 from public.environments e where e.project_id=v_project.id and e.kind='production' and e.status='ready') then raise exception 'ready production environment metadata required for release-candidate verification'; end if;
 perform set_config('vrs.certification_depth_authorized','true',true);
 for i in 1..p_run_count loop
  insert into public.workflows(project_id,app_spec_id,workflow_type,state,input,created_by) values(v_project.id,v_spec.id,'factory_build_v2','queued',jsonb_build_object('builder_key',p_builder_key,'target_environment','staging','target_platforms',to_jsonb(v_profile.target_platforms),'certification_depth_run',true,'certification_batch_index',i,'production_locked',true),v_actor) returning id into v_workflow_id;
  insert into public.factory_runs(project_id,app_spec_id,workflow_id,requested_by,run_type,state,target_environment,production_locked,input,plan,target_platforms) values(v_project.id,v_spec.id,v_workflow_id,v_actor,'build','planning','staging',true,jsonb_build_object('builder_key',p_builder_key,'generator_version','certification-depth-v1','certification_depth_run',true,'certification_batch_index',i),jsonb_build_object('purpose','current-policy-certification-depth','builder_key',p_builder_key,'builders',jsonb_build_array(jsonb_build_object('key',p_builder_key))),v_profile.target_platforms) returning id into v_run_id;
  v_ids:=v_ids||jsonb_build_array(jsonb_build_object('factory_run_id',v_run_id,'workflow_id',v_workflow_id,'builder_key',p_builder_key,'target_environment','staging','production_locked',true));
 end loop;
 return jsonb_build_object('ok',true,'builder_key',p_builder_key,'run_count',p_run_count,'runs',v_ids,'production_locked',true,'production_approval_performed',false,'production_promotion_performed',false,'public_customer_quota_consumed',false);
end;$$;


ALTER FUNCTION "public"."enqueue_vrs_golden_certification_runs"("p_builder_key" "text", "p_run_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."evaluate_builder_certification"("p_builder_key" "text", "p_activate" boolean DEFAULT false) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  pol public.builder_certification_policies%rowtype;
  req text[];
  passed text[];
  missing text[];
  req_count int;
  pass_count int;
  run_count int;
  v_score numeric;
  v_decision text;
  v_status text;
begin
  select * into pol from public.builder_certification_policies where builder_key=p_builder_key and status='active';
  if not found then raise exception 'No active certification policy for builder %', p_builder_key; end if;

  select coalesce(array_agg(value order by value),'{}'::text[]) into req
  from jsonb_array_elements_text(pol.required_evidence);

  select coalesce(array_agg(distinct evidence_type order by evidence_type),'{}'::text[]) into passed
  from public.builder_certification_evidence
  where builder_key=p_builder_key and evidence_status='pass' and evidence_type = any(req);

  select coalesce(array_agg(x order by x),'{}'::text[]) into missing
  from unnest(req) x where not (x = any(passed));

  req_count := cardinality(req);
  pass_count := cardinality(passed);

  select count(*)::int into run_count
  from (
    select factory_run_id
    from public.builder_certification_evidence
    where builder_key=p_builder_key
      and evidence_status='pass'
      and factory_run_id is not null
      and evidence_type = any(req)
    group by factory_run_id
    having count(distinct evidence_type) = req_count
  ) complete_runs;

  v_score := case when req_count=0 then 0 else pass_count::numeric/req_count::numeric end;

  if cardinality(missing)=0 and run_count >= pol.minimum_distinct_runs and v_score >= pol.minimum_score then
    v_decision := 'certified';
  elsif pass_count > 0 then
    v_decision := 'candidate';
  else
    v_decision := 'not_ready';
  end if;

  insert into public.builder_certification_results(builder_key,decision,score,passed_evidence,missing_evidence,distinct_run_count,metadata)
  values(p_builder_key,v_decision,v_score,passed,missing,run_count,jsonb_build_object('policy_id',pol.id,'activation_requested',p_activate,'depth_semantics','complete_required_evidence_per_factory_run'));

  if p_activate and v_decision='certified' and pol.allow_auto_activate then
    perform set_config('vrs.certification_activation','allow',true);
    update public.builder_registry set status='active',updated_at=now() where builder_key=p_builder_key and status <> 'active';
  end if;

  select status into v_status from public.builder_registry where builder_key=p_builder_key;

  return jsonb_build_object('builder_key',p_builder_key,'decision',v_decision,'score',v_score,'passed_evidence',passed,'missing_evidence',missing,'distinct_run_count',run_count,'depth_semantics','complete_required_evidence_per_factory_run','builder_status',v_status,'activated',(p_activate and v_decision='certified' and pol.allow_auto_activate));
end;
$$;


ALTER FUNCTION "public"."evaluate_builder_certification"("p_builder_key" "text", "p_activate" boolean) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."evaluate_vrs_release_server_gates"("p_factory_run_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'extensions', 'pg_temp'
    AS $$
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

  -- Post-candidate authority MUST be the frozen deployment snapshot, never live policy.
  v_required:=private.get_deployment_required_gates(v_dep.id);
  if v_required is null or jsonb_typeof(v_required) <> 'array' or jsonb_array_length(v_required)=0 then
    raise exception 'deployment required-gates snapshot missing or invalid';
  end if;

  -- Snapshot integrity checks fail closed.
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
    select count(*) into v_bad_definer from pg_proc p join pg_namespace n on n.oid=p.pronamespace
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
    v_pwa_offline_ok := coalesce(v_sw,'') like '%caches.open%' and coalesce(v_sw,'') like '%cache.put%' and coalesce(v_sw,'') like '%caches.match%' and coalesce(v_manifest,'') <> '';
    update public.release_gates set status=case when v_pwa_offline_ok then 'pass' else 'fail' end,
      score=case when v_pwa_offline_ok then 1 else 0 end,
      evidence=jsonb_build_object('scope','generated_pwa_offline_contract','manifest_present',coalesce(v_manifest,'')<>'','cache_open',coalesce(v_sw,'') like '%caches.open%','cache_put',coalesce(v_sw,'') like '%cache.put%','cache_match',coalesce(v_sw,'') like '%caches.match%','checked_by','server_gate_evaluator','required_gates_authority','deployment_snapshot','deployment_id',v_dep.id),checked_at=now(),checked_by=null
      where factory_run_id=v_run.id and gate_key='offline_pwa_contract';
    v_results:=v_results||jsonb_build_array(jsonb_build_object('key','offline_pwa_contract','status',case when v_pwa_offline_ok then 'pass' else 'fail' end));
  end if;

  return jsonb_build_object('factory_run_id',v_run.id,'deployment_id',v_dep.id,'required_gates_authority','deployment_snapshot','required_gates_snapshot',v_required,'server_gate_results',v_results);
end $$;


ALTER FUNCTION "public"."evaluate_vrs_release_server_gates"("p_factory_run_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_vrs_billplz_production_readiness"() RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ select private.billplz_production_readiness(); $$;


ALTER FUNCTION "public"."get_vrs_billplz_production_readiness"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_vrs_notification_production_readiness"() RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'auth', 'pg_temp'
    AS $$ select private.notification_production_readiness(); $$;


ALTER FUNCTION "public"."get_vrs_notification_production_readiness"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."guard_builder_activation"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public', 'pg_temp'
    AS $$
begin
  if new.status='active' and old.status is distinct from 'active' then
    if coalesce(current_setting('vrs.certification_activation', true),'') <> 'allow' then
      raise exception 'Builder activation requires certification engine approval';
    end if;
  end if;
  return new;
end;
$$;


ALTER FUNCTION "public"."guard_builder_activation"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."harvest_exact_release_gate_certification_evidence"("p_factory_run_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public', 'private'
    AS $$
declare
  v_run public.factory_runs%rowtype;
  v_dep public.deployments%rowtype;
  v_builder text;
  v_required text[];
  v_missing text[];
  v_inserted int := 0;
  v_result jsonb;
  r record;
begin
  select * into v_run from public.factory_runs where id=p_factory_run_id;
  if not found then raise exception 'factory run not found'; end if;
  select * into v_dep from public.deployments where factory_run_id=p_factory_run_id order by created_at desc limit 1;
  if not found then raise exception 'deployment not found'; end if;
  v_builder := v_dep.builder_key_snapshot;
  if v_builder not in ('web-react-v1','pwa-react-v1','api-service-v1') then raise exception 'builder % is not eligible for exact gate harvesting', v_builder; end if;
  if v_run.target_environment <> 'staging' or v_run.production_locked is not true then raise exception 'certification evidence requires staging + production_locked'; end if;
  if v_run.state <> 'awaiting_approval' then raise exception 'factory run must be awaiting_approval, got %', v_run.state; end if;
  if v_dep.status <> 'certified' or v_dep.artifact_sha256 is null then raise exception 'deployment must be certified with immutable artifact sha'; end if;
  if not exists (select 1 from public.release_gates where factory_run_id=p_factory_run_id and gate_key='supply_chain_attestation' and status='pass' and score=1) then raise exception 'mandatory supply_chain_attestation is not PASS'; end if;
  select coalesce(array_agg(value order by value),'{}'::text[]) into v_required
  from public.builder_certification_policies p, lateral jsonb_array_elements_text(p.required_evidence)
  where p.builder_key=v_builder and p.status='active';
  if cardinality(v_required)=0 then raise exception 'no active certification evidence policy for %',v_builder; end if;
  select coalesce(array_agg(req order by req),'{}'::text[]) into v_missing
  from unnest(v_required) req
  where not exists (select 1 from public.release_gates g where g.factory_run_id=p_factory_run_id and g.gate_key=req and g.status='pass' and g.score=1);
  if cardinality(v_missing)>0 then raise exception 'required exact-match release gates are not all PASS: %',v_missing; end if;
  for r in select g.id,g.gate_key,g.gate_type,g.score,g.evidence,g.checked_at from public.release_gates g where g.factory_run_id=p_factory_run_id and g.gate_key=any(v_required) and g.status='pass' and g.score=1 order by g.gate_key
  loop
    if not exists (select 1 from public.builder_certification_evidence e where e.builder_key=v_builder and e.factory_run_id=p_factory_run_id and e.evidence_type=r.gate_key and e.evidence_status='pass') then
      insert into public.builder_certification_evidence(builder_key,factory_run_id,project_id,evidence_type,evidence_status,evidence,source_uri)
      values(v_builder,p_factory_run_id,v_run.project_id,r.gate_key,'pass',jsonb_build_object('source','certified_release_gate','release_gate_id',r.id,'gate_type',r.gate_type,'gate_score',r.score,'gate_checked_at',r.checked_at,'artifact_sha256',v_dep.artifact_sha256,'gate_evidence',r.evidence,'supply_chain_required',true),format('vl://release-gate/%s',r.id));
      v_inserted := v_inserted + 1;
    end if;
  end loop;
  select public.evaluate_builder_certification(v_builder,false) into v_result;
  return jsonb_build_object('ok',true,'factory_run_id',p_factory_run_id,'builder_key',v_builder,'inserted',v_inserted,'required_evidence',v_required,'certification',v_result);
end;
$$;


ALTER FUNCTION "public"."harvest_exact_release_gate_certification_evidence"("p_factory_run_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ingest_ci_evidence"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_external_run_id" "text", "p_external_job_id" "text", "p_head_sha" "text", "p_run_status" "text", "p_run_conclusion" "text", "p_step_results" "jsonb", "p_artifact_results" "jsonb" DEFAULT '{}'::"jsonb", "p_raw_summary" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_static text;
  v_test text;
  v_apk text;
  v_result jsonb;
begin
  if not exists (select 1 from public.project_members where project_id=p_project_id and user_id=auth.uid()) then
    raise exception 'forbidden';
  end if;

  insert into public.ci_evidence_ingestions(project_id,factory_run_id,builder_key,repository,external_run_id,external_job_id,head_sha,run_status,run_conclusion,step_results,artifact_results,raw_summary)
  values(p_project_id,p_factory_run_id,p_builder_key,p_repository,p_external_run_id,p_external_job_id,p_head_sha,p_run_status,p_run_conclusion,coalesce(p_step_results,'{}'::jsonb),coalesce(p_artifact_results,'{}'::jsonb),coalesce(p_raw_summary,'{}'::jsonb))
  on conflict(provider,repository,external_run_id,builder_key) do update set
    external_job_id=excluded.external_job_id,
    head_sha=excluded.head_sha,
    run_status=excluded.run_status,
    run_conclusion=excluded.run_conclusion,
    step_results=excluded.step_results,
    artifact_results=excluded.artifact_results,
    raw_summary=excluded.raw_summary,
    ingested_at=now();

  v_static := coalesce(p_step_results->>'Analyze','');
  v_test := coalesce(p_step_results->>'Test','');
  v_apk := coalesce(p_step_results->>'Build debug APK','');

  if v_static='success' and not exists (
    select 1 from public.builder_certification_evidence where builder_key=p_builder_key and evidence_type='static_analysis_pass' and source_uri=format('https://github.com/%s/actions/runs/%s',p_repository,p_external_run_id)
  ) then
    insert into public.builder_certification_evidence(builder_key,factory_run_id,project_id,evidence_type,evidence_status,evidence,source_uri)
    values(p_builder_key,p_factory_run_id,p_project_id,'static_analysis_pass','pass',jsonb_build_object('provider','github_actions','run_id',p_external_run_id,'head_sha',p_head_sha),format('https://github.com/%s/actions/runs/%s',p_repository,p_external_run_id));
  end if;

  if v_test='success' and not exists (
    select 1 from public.builder_certification_evidence where builder_key=p_builder_key and evidence_type='test_pass' and source_uri=format('https://github.com/%s/actions/runs/%s',p_repository,p_external_run_id)
  ) then
    insert into public.builder_certification_evidence(builder_key,factory_run_id,project_id,evidence_type,evidence_status,evidence,source_uri)
    values(p_builder_key,p_factory_run_id,p_project_id,'test_pass','pass',jsonb_build_object('provider','github_actions','run_id',p_external_run_id,'head_sha',p_head_sha),format('https://github.com/%s/actions/runs/%s',p_repository,p_external_run_id));
  end if;

  if v_apk='success' and coalesce(p_artifact_results->>'fieldgis-reference-debug-apk','')='present' and not exists (
    select 1 from public.builder_certification_evidence where builder_key=p_builder_key and evidence_type='apk_build_pass' and source_uri=format('https://github.com/%s/actions/runs/%s',p_repository,p_external_run_id)
  ) then
    insert into public.builder_certification_evidence(builder_key,factory_run_id,project_id,evidence_type,evidence_status,evidence,source_uri)
    values(p_builder_key,p_factory_run_id,p_project_id,'apk_build_pass','pass',jsonb_build_object('provider','github_actions','run_id',p_external_run_id,'head_sha',p_head_sha,'artifact','fieldgis-reference-debug-apk'),format('https://github.com/%s/actions/runs/%s',p_repository,p_external_run_id));
  end if;

  select public.evaluate_builder_certification(p_builder_key,false) into v_result;
  return jsonb_build_object('ingested',true,'certification',v_result);
end;
$$;


ALTER FUNCTION "public"."ingest_ci_evidence"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_external_run_id" "text", "p_external_job_id" "text", "p_head_sha" "text", "p_run_status" "text", "p_run_conclusion" "text", "p_step_results" "jsonb", "p_artifact_results" "jsonb", "p_raw_summary" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."learn_from_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  a public.ci_repair_actions%rowtype;
  s int;
  f int;
  c numeric;
begin
  select * into a from public.ci_repair_actions where id=p_action_id;
  if not found then raise exception 'repair action not found'; end if;
  if not exists (select 1 from public.project_members where project_id=a.project_id and user_id=auth.uid()) then raise exception 'forbidden'; end if;

  update public.ci_repair_actions
  set state=case when p_success then 'verified' else 'failed' end,
      execution_result=coalesce(execution_result,'{}'::jsonb)||jsonb_build_object('verification',coalesce(p_details,'{}'::jsonb)),
      verified_at=case when p_success then now() else verified_at end,
      updated_at=now()
  where id=p_action_id;

  update public.repair_recipe_registry
  set success_count=success_count + case when p_success then 1 else 0 end,
      failure_count=failure_count + case when p_success then 0 else 1 end,
      last_verified_at=now(),
      confidence=least(0.99,greatest(0.05,
        ((success_count + case when p_success then 1 else 0 end + 1)::numeric /
         (success_count + failure_count + 3)::numeric)
      )),
      updated_at=now()
  where recipe_key=a.recipe_key
  returning success_count,failure_count,confidence into s,f,c;

  return jsonb_build_object('ok',true,'repair_action_id',p_action_id,'recipe_key',a.recipe_key,'success',p_success,'success_count',s,'failure_count',f,'confidence',c);
end;
$$;


ALTER FUNCTION "public"."learn_from_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."mark_ci_repair_applied"("p_action_id" "uuid", "p_execution_result" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare a public.ci_repair_actions%rowtype;
begin
  select * into a from public.ci_repair_actions where id=p_action_id;
  if not found then raise exception 'repair action not found'; end if;
  if not exists (select 1 from public.project_members where project_id=a.project_id and user_id=auth.uid()) then raise exception 'forbidden'; end if;
  if a.risk_level <> 'low' and a.state <> 'approved' then raise exception 'human approval required'; end if;
  update public.ci_repair_actions
    set state='applied', execution_result=coalesce(p_execution_result,'{}'::jsonb), applied_at=now(), updated_at=now()
  where id=p_action_id;
  return jsonb_build_object('ok',true,'repair_action_id',p_action_id,'state','applied');
end;
$$;


ALTER FUNCTION "public"."mark_ci_repair_applied"("p_action_id" "uuid", "p_execution_result" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."mark_ci_repair_retry"("p_action_id" "uuid", "p_retry_run_id" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare a public.ci_repair_actions%rowtype;
begin
  select * into a from public.ci_repair_actions where id=p_action_id;
  if not found then raise exception 'repair action not found'; end if;
  if not exists (select 1 from public.project_members where project_id=a.project_id and user_id=auth.uid()) then raise exception 'forbidden'; end if;
  update public.ci_repair_actions set state='retrying',retry_run_id=p_retry_run_id,updated_at=now() where id=p_action_id;
  return jsonb_build_object('ok',true,'repair_action_id',p_action_id,'state','retrying','retry_run_id',p_retry_run_id);
end;
$$;


ALTER FUNCTION "public"."mark_ci_repair_retry"("p_action_id" "uuid", "p_retry_run_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."propose_ci_repair"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_branch" "text", "p_failure_class" "text", "p_signature" "text", "p_error_text" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare
  r public.repair_recipe_registry%rowtype;
  a public.ci_repair_actions%rowtype;
begin
  if not exists (select 1 from public.project_members where project_id=p_project_id and user_id=auth.uid()) then
    raise exception 'forbidden';
  end if;

  select * into r
  from public.repair_recipe_registry
  where status='active'
    and failure_class=p_failure_class
    and (builder_key is null or builder_key=p_builder_key)
    and (p_signature ilike '%'||signature_pattern||'%' or p_error_text ilike '%'||signature_pattern||'%')
  order by case when builder_key=p_builder_key then 0 else 1 end, auto_apply desc, updated_at desc
  limit 1;

  if not found then
    return jsonb_build_object('matched',false,'reason','no_recipe');
  end if;

  insert into public.ci_repair_actions(project_id,factory_run_id,builder_key,recipe_key,repository,branch,risk_level,auto_apply,state,repair_plan)
  values(
    p_project_id,p_factory_run_id,p_builder_key,r.recipe_key,p_repository,coalesce(nullif(p_branch,''),'main'),r.risk_level,
    (r.auto_apply and r.risk_level='low'),
    case when r.auto_apply and r.risk_level='low' then 'approved' else 'proposed' end,
    jsonb_build_object(
      'action_type',r.action_type,
      'action_spec',r.action_spec,
      'failure_class',p_failure_class,
      'signature',left(p_signature,500),
      'error_excerpt',left(p_error_text,2000),
      'production_locked',true
    )
  ) returning * into a;

  return jsonb_build_object(
    'matched',true,
    'repair_action_id',a.id,
    'recipe_key',a.recipe_key,
    'risk_level',a.risk_level,
    'auto_apply',a.auto_apply,
    'state',a.state,
    'repair_plan',a.repair_plan
  );
end;
$$;


ALTER FUNCTION "public"."propose_ci_repair"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_branch" "text", "p_failure_class" "text", "p_signature" "text", "p_error_text" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."reconcile_factory_artifact_physical_provenance"("p_factory_run_id" "uuid", "p_github_run_id" "text", "p_github_artifact_id" "text", "p_github_artifact_digest" "text", "p_github_head_sha" "text", "p_github_artifact_expires_at" timestamp with time zone, "p_artifact_name" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $_$
declare
  v_art public.factory_artifacts%rowtype;
  v_run public.factory_runs%rowtype;
  v_existing jsonb;
begin
  if p_factory_run_id is null then raise exception 'factory_run_id required'; end if;
  if coalesce(trim(p_github_run_id),'') !~ '^[0-9]+$' then raise exception 'valid github_run_id required'; end if;
  if coalesce(trim(p_github_artifact_id),'') !~ '^[0-9]+$' then raise exception 'valid github_artifact_id required'; end if;
  if coalesce(trim(p_github_artifact_digest),'') !~ '^sha256:[0-9a-fA-F]{64}$' then raise exception 'valid GitHub artifact digest required'; end if;
  if coalesce(trim(p_github_head_sha),'') !~ '^[0-9a-fA-F]{40}$' then raise exception 'valid GitHub head SHA required'; end if;
  if p_github_artifact_expires_at is null or p_github_artifact_expires_at <= now() then raise exception 'non-expired GitHub artifact required'; end if;
  if coalesce(trim(p_artifact_name),'')='' then raise exception 'artifact name required'; end if;

  select * into v_run from public.factory_runs where id=p_factory_run_id for update;
  if not found then raise exception 'factory run not found'; end if;

  select * into v_art from public.factory_artifacts
   where factory_run_id=p_factory_run_id and artifact_type='bundle' and name=p_artifact_name
   order by created_at desc limit 1 for update;
  if not found then raise exception 'factory bundle artifact not found'; end if;

  if coalesce(v_art.metadata->>'github_run_id','')<>p_github_run_id then
    raise exception 'GitHub run binding mismatch';
  end if;

  if coalesce(v_run.result#>>'{runner,github_sha}','')<>'' and lower(v_run.result#>>'{runner,github_sha}')<>lower(p_github_head_sha) then
    raise exception 'GitHub head SHA does not match runner source commit';
  end if;

  v_existing:=coalesce(v_art.metadata,'{}'::jsonb);
  if nullif(v_existing->>'github_artifact_id','') is not null then
    if v_existing->>'github_artifact_id'<>p_github_artifact_id
       or lower(v_existing->>'github_artifact_digest')<>lower(p_github_artifact_digest)
       or lower(v_existing->>'github_head_sha')<>lower(p_github_head_sha) then
      raise exception 'physical artifact provenance is already bound and immutable';
    end if;
    return jsonb_build_object('decision','already_reconciled','artifact_id',v_art.id,'factory_run_id',p_factory_run_id,'idempotent',true);
  end if;

  update public.factory_artifacts
  set metadata=v_existing||jsonb_build_object(
    'github_artifact_id',p_github_artifact_id,
    'github_artifact_digest',lower(p_github_artifact_digest),
    'github_head_sha',lower(p_github_head_sha),
    'github_artifact_expires_at',p_github_artifact_expires_at,
    'physical_provenance_reconciled_at',now(),
    'physical_provenance_source','github-actions-api'
  ) where id=v_art.id;

  insert into private.factory_execution_events(factory_run_id,project_id,event_type,from_state,to_state,payload)
  values(v_run.id,v_run.project_id,'artifact_physical_provenance_reconciled',v_run.state,v_run.state,
    jsonb_build_object('artifact_id',v_art.id,'github_artifact_id',p_github_artifact_id,'github_artifact_digest',lower(p_github_artifact_digest),'github_head_sha',lower(p_github_head_sha),'expires_at',p_github_artifact_expires_at));

  return jsonb_build_object('decision','reconciled','artifact_id',v_art.id,'factory_run_id',p_factory_run_id,'github_artifact_id',p_github_artifact_id,'idempotent',false);
end
$_$;


ALTER FUNCTION "public"."reconcile_factory_artifact_physical_provenance"("p_factory_run_id" "uuid", "p_github_run_id" "text", "p_github_artifact_id" "text", "p_github_artifact_digest" "text", "p_github_head_sha" "text", "p_github_artifact_expires_at" timestamp with time zone, "p_artifact_name" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."record_vrs_supply_chain_attestation"("p_factory_run_id" "uuid", "p_artifact_sha256" "text", "p_github_run_id" "text", "p_build_workflow_run_id" "text", "p_provenance_verified" boolean, "p_sbom_verified" boolean, "p_sbom_sha256" "text", "p_evidence" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $_$
declare
  v_dep public.deployments%rowtype;
  v_gate public.release_gates%rowtype;
begin
  if p_factory_run_id is null then raise exception 'factory_run_id required'; end if;
  if coalesce(p_artifact_sha256,'') !~ '^[0-9a-fA-F]{64}$' then raise exception 'valid artifact SHA-256 required'; end if;
  if coalesce(p_sbom_sha256,'') !~ '^[0-9a-fA-F]{64}$' then raise exception 'valid SBOM SHA-256 required'; end if;
  if p_provenance_verified is distinct from true or p_sbom_verified is distinct from true then
    raise exception 'cryptographic provenance and SBOM verification are both required';
  end if;
  if nullif(p_github_run_id,'') is null or nullif(p_build_workflow_run_id,'') is null then
    raise exception 'GitHub attestation and build run identifiers required';
  end if;

  select * into v_dep
  from public.deployments
  where factory_run_id=p_factory_run_id
  order by created_at desc
  limit 1
  for update;
  if not found then raise exception 'deployment not found for factory run'; end if;
  if lower(coalesce(v_dep.artifact_sha256,'')) <> lower(p_artifact_sha256) then
    raise exception 'attested artifact SHA-256 does not match deployment';
  end if;

  select * into v_gate
  from public.release_gates
  where factory_run_id=p_factory_run_id and gate_key='supply_chain_attestation'
  for update;
  if not found then raise exception 'mandatory supply_chain_attestation gate not initialized'; end if;

  perform set_config('vrs.supply_chain_authorized','true',true);
  update public.release_gates
     set status='pass',
         score=1,
         checked_at=now(),
         checked_by=null,
         evidence=jsonb_build_object(
           'source','github_oidc_supply_chain_attestation',
           'artifact_sha256',lower(p_artifact_sha256),
           'sbom_sha256',lower(p_sbom_sha256),
           'provenance_verified',true,
           'sbom_verified',true,
           'attestation_workflow_run_id',p_github_run_id,
           'build_workflow_run_id',p_build_workflow_run_id,
           'verified_at',now()
         ) || coalesce(p_evidence,'{}'::jsonb)
   where factory_run_id=p_factory_run_id and gate_key='supply_chain_attestation';

  return jsonb_build_object(
    'status','pass',
    'gate_key','supply_chain_attestation',
    'factory_run_id',p_factory_run_id,
    'deployment_id',v_dep.id,
    'artifact_sha256',lower(p_artifact_sha256),
    'sbom_sha256',lower(p_sbom_sha256),
    'mandatory',true
  );
end;
$_$;


ALTER FUNCTION "public"."record_vrs_supply_chain_attestation"("p_factory_run_id" "uuid", "p_artifact_sha256" "text", "p_github_run_id" "text", "p_build_workflow_run_id" "text", "p_provenance_verified" boolean, "p_sbom_verified" boolean, "p_sbom_sha256" "text", "p_evidence" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."recover_exhausted_certification_depth_validation"("p_factory_run_id" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_run public.factory_runs%rowtype;
  v_dep public.deployments%rowtype;
  v_job private.release_validation_jobs%rowtype;
  v_missing integer;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role required';
  end if;

  select * into v_run from public.factory_runs where id=p_factory_run_id for update;
  if not found
     or coalesce((v_run.input->>'certification_depth_run')::boolean,false) is distinct from true
     or v_run.target_environment <> 'staging'
     or v_run.production_locked is distinct from true
     or v_run.state <> 'validating' then
    raise exception 'factory run is not an eligible certification-depth validation';
  end if;

  select * into v_dep from public.deployments where factory_run_id=v_run.id for update;
  if not found or v_dep.status <> 'planned' then
    raise exception 'deployment is not planned';
  end if;

  select * into v_job from private.release_validation_jobs where deployment_id=v_dep.id for update;
  if not found or v_job.state <> 'queued' or v_job.attempts < v_job.max_attempts then
    raise exception 'validation job is not exhausted';
  end if;

  select count(*) into v_missing
  from jsonb_array_elements(v_dep.required_gates_snapshot) req(item)
  left join public.release_gates g
    on g.factory_run_id=v_run.id and g.gate_key=(req.item->>'key')
  where (req.item->>'key') not in ('human_production_approval','production_lock')
    and coalesce(g.status,'pending') <> 'pass';

  if v_missing <> 0 then
    raise exception 'technical frozen gates are not all pass';
  end if;

  update private.release_validation_jobs
  set max_attempts=max_attempts+1,
      error_text='controlled certification-depth recovery after all technical frozen gates passed',
      updated_at=now()
  where id=v_job.id;

  return jsonb_build_object(
    'ok',true,
    'factory_run_id',v_run.id,
    'job_id',v_job.id,
    'attempts',v_job.attempts,
    'max_attempts',v_job.max_attempts+1,
    'scope','certification_depth_staging_only'
  );
end
$$;


ALTER FUNCTION "public"."recover_exhausted_certification_depth_validation"("p_factory_run_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."reject_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  return private.reject_production_release(p_deployment_id,p_rationale);
end
$$;


ALTER FUNCTION "public"."reject_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."request_vrs_internal_usage_override"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer DEFAULT 60) RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "public"."request_vrs_internal_usage_override"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."request_vrs_production_rollback"("p_deployment_id" "uuid", "p_reason" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  return private.request_production_rollback(p_deployment_id,p_reason);
end
$$;


ALTER FUNCTION "public"."request_vrs_production_rollback"("p_deployment_id" "uuid", "p_reason" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."touch_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


ALTER FUNCTION "public"."touch_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."verify_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb" DEFAULT '{}'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
declare a public.ci_repair_actions%rowtype;
begin
  select * into a from public.ci_repair_actions where id=p_action_id;
  if not found then raise exception 'repair action not found'; end if;
  if not exists (select 1 from public.project_members where project_id=a.project_id and user_id=auth.uid()) then raise exception 'forbidden'; end if;
  update public.ci_repair_actions
    set state=case when p_success then 'verified' else 'failed' end,
        execution_result=coalesce(execution_result,'{}'::jsonb)||jsonb_build_object('verification',coalesce(p_details,'{}'::jsonb)),
        verified_at=case when p_success then now() else verified_at end,
        updated_at=now()
    where id=p_action_id;
  return jsonb_build_object('ok',true,'repair_action_id',p_action_id,'state',case when p_success then 'verified' else 'failed' end);
end;
$$;


ALTER FUNCTION "public"."verify_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_apply_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
declare
  v_order private.payment_production_orders%rowtype;
  v_event private.payment_production_webhook_events%rowtype;
  v_applied boolean := false;
  v_reason text := 'no_state_change';
begin
  if current_user not in ('service_role','postgres') then raise exception 'service role required'; end if;
  if p_normalized_status not in ('paid','pending','cancelled','refunded') then raise exception 'invalid normalized status'; end if;

  select * into v_order from private.payment_production_orders where provider_bill_id=p_provider_bill_id for update;
  if not found then raise exception 'unknown production test bill'; end if;
  if v_order.purpose<>'controlled_live_test' or v_order.amount_minor<>100 or v_order.currency<>'MYR' then raise exception 'production test invariant failed'; end if;
  if p_amount_minor<>v_order.amount_minor then raise exception 'amount mismatch'; end if;

  select * into v_event from private.payment_production_webhook_events where event_key=p_event_key;
  if found then
    return jsonb_build_object('ok',true,'duplicate',true,'applied',false,'status',v_order.status,'order_id',v_order.id,'reason','duplicate_event');
  end if;

  if p_normalized_status='paid' then
    if v_order.status='pending' and v_order.fulfillment_state='unfulfilled' then
      update private.payment_production_orders
         set status='paid',paid_at=coalesce(paid_at,now()),fulfillment_state='fulfilled',updated_at=now()
       where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
      v_applied := found;
      if v_applied then
        insert into private.payment_production_fulfillment_events(order_id,action_key,status,evidence)
        values(v_order.id,'billplz-production-test:'||v_order.id::text,'fulfilled',jsonb_build_object('payment_status','paid','amount_minor',100,'currency','MYR','provider_bill_id',p_provider_bill_id,'exactly_once',true))
        on conflict(action_key) do nothing;
      end if;
      v_reason := case when v_applied then 'pending_to_paid_fulfilled' else 'race_blocked' end;
    elsif v_order.status in ('cancelled','refunded') then
      v_reason := 'terminal_order_not_resurrected';
    else
      v_reason := 'paid_state_unchanged';
    end if;
  elsif p_normalized_status='cancelled' then
    update private.payment_production_orders set status='cancelled',updated_at=now()
     where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'pending_to_cancelled' else 'cancellation_not_applicable' end;
  elsif p_normalized_status='refunded' then
    update private.payment_production_orders
       set status='refunded',fulfillment_state='reversed',updated_at=now()
     where id=v_order.id and status='paid' and fulfillment_state='fulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'paid_to_refunded_reversed' else 'refund_not_applicable' end;
  end if;

  insert into private.payment_production_webhook_events(event_key,provider_bill_id,payload_sha256,signature_valid,normalized_status,amount_minor,applied,duplicate,processed_at,metadata)
  values(p_event_key,p_provider_bill_id,p_payload_sha256,true,p_normalized_status,p_amount_minor,v_applied,false,now(),jsonb_build_object('environment','production','purpose','controlled_live_test','reason',v_reason));

  return jsonb_build_object('ok',true,'duplicate',false,'applied',v_applied,'status',p_normalized_status,'order_id',v_order.id,'reason',v_reason);
end;
$$;


ALTER FUNCTION "public"."vl_apply_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ begin return private.apply_billplz_sandbox_webhook(p_event_key,p_provider_bill_id,p_payload_sha256,p_normalized_status,p_amount_minor); end $$;


ALTER FUNCTION "public"."vl_apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_apply_resend_sandbox_webhook"("p_event_key" "text", "p_provider_message_id" "text", "p_event_type" "text", "p_status" "text", "p_payload_sha256" "text") RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ select private.apply_resend_sandbox_webhook(p_event_key,p_provider_message_id,p_event_type,p_status,p_payload_sha256) $$;


ALTER FUNCTION "public"."vl_apply_resend_sandbox_webhook"("p_event_key" "text", "p_provider_message_id" "text", "p_event_type" "text", "p_status" "text", "p_payload_sha256" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_billplz_ci_mark_cancelled"("p_order_id" "uuid") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ declare v_count integer; begin update private.payment_sandbox_orders set status='cancelled',updated_at=now() where id=p_order_id and environment='sandbox' and adapter_key='billplz-payment-v1' and status='pending' and fulfillment_state='unfulfilled'; get diagnostics v_count=row_count; return v_count=1; end $$;


ALTER FUNCTION "public"."vl_billplz_ci_mark_cancelled"("p_order_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_billplz_ci_record_order"("p_provider_bill_id" "text", "p_merchant_reference" "text", "p_checkout_url" "text", "p_github_run_id" "text", "p_github_sha" "text", "p_workflow_ref" "text") RETURNS "uuid"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ declare v_id uuid; begin if coalesce(trim(p_provider_bill_id),'')='' then raise exception 'provider_bill_id required'; end if; insert into private.payment_sandbox_orders(adapter_key,provider_bill_id,merchant_reference,amount_minor,currency,environment,status,fulfillment_state,checkout_url,metadata) values('billplz-payment-v1',p_provider_bill_id,p_merchant_reference,100,'MYR','sandbox','pending','unfulfilled',p_checkout_url,jsonb_build_object('source','github_oidc_cert','github_run_id',p_github_run_id,'github_sha',p_github_sha,'workflow_ref',p_workflow_ref,'pii_stored',false)) returning id into v_id; return v_id; end $$;


ALTER FUNCTION "public"."vl_billplz_ci_record_order"("p_provider_bill_id" "text", "p_merchant_reference" "text", "p_checkout_url" "text", "p_github_run_id" "text", "p_github_sha" "text", "p_workflow_ref" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_billplz_ci_record_reconciliation"("p_order_id" "uuid", "p_provider_bill_id" "text", "p_provider_status" "text", "p_provider_amount_minor" integer, "p_provider_http_status" integer, "p_paid" boolean, "p_pass" boolean) RETURNS "void"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ begin insert into private.payment_reconciliation_checks(adapter_key,order_id,provider_bill_id,expected_status,provider_status,expected_amount_minor,provider_amount_minor,status,evidence) values('billplz-payment-v1',p_order_id,p_provider_bill_id,'pending',p_provider_status,100,p_provider_amount_minor,case when p_pass then 'pass' else 'fail' end,jsonb_build_object('source','github_oidc_cert','provider_http_status',p_provider_http_status,'paid',p_paid)); end $$;


ALTER FUNCTION "public"."vl_billplz_ci_record_reconciliation"("p_order_id" "uuid", "p_provider_bill_id" "text", "p_provider_status" "text", "p_provider_amount_minor" integer, "p_provider_http_status" integer, "p_paid" boolean, "p_pass" boolean) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_fulfill_verified_sandbox_payment"("p_order_id" "uuid", "p_action_key" "text") RETURNS "jsonb"
    LANGUAGE "sql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ select private.fulfill_verified_sandbox_payment(p_order_id,p_action_key) $$;


ALTER FUNCTION "public"."vl_fulfill_verified_sandbox_payment"("p_order_id" "uuid", "p_action_key" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_get_assisted_build_quote"("p_complexity" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "public"."vl_get_assisted_build_quote"("p_complexity" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_prepare_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE
    SET "search_path" TO ''
    AS $$
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


ALTER FUNCTION "public"."vl_prepare_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."vl_prepare_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") IS 'Authenticated read-only preparation of canonical product-alignment evidence for Assisted Build review. No factory run or production authority mutation.';



CREATE OR REPLACE FUNCTION "public"."vl_record_invalid_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$
begin
  if current_user not in ('service_role','postgres') then raise exception 'service role required'; end if;
  insert into private.payment_production_webhook_events(event_key,provider_bill_id,payload_sha256,signature_valid,normalized_status,amount_minor,applied,duplicate,error_text,metadata)
  values(p_event_key,p_provider_bill_id,p_payload_sha256,false,p_normalized_status,p_amount_minor,false,false,'invalid signature',jsonb_build_object('environment','production','purpose','controlled_live_test'))
  on conflict(event_key) do nothing;
  return jsonb_build_object('ok',true,'recorded',true);
end$$;


ALTER FUNCTION "public"."vl_record_invalid_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_record_invalid_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ declare v_inserted boolean:=false; begin if coalesce(trim(p_event_key),'')='' then raise exception 'event_key required'; end if; insert into private.payment_webhook_events(adapter_key,event_key,provider_bill_id,payload_sha256,signature_valid,normalized_status,amount_minor,applied,duplicate,error_text,processed_at,metadata) values('billplz-payment-v1',p_event_key,nullif(p_provider_bill_id,''),p_payload_sha256,false,p_normalized_status,case when p_amount_minor>0 then p_amount_minor else null end,false,false,'invalid_signature',now(),jsonb_build_object('environment','sandbox')) on conflict(event_key) do nothing; get diagnostics v_inserted=row_count; return v_inserted; end $$;


ALTER FUNCTION "public"."vl_record_invalid_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_resend_reconciliation_source_check"("p_provider_message_id" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'pg_catalog', 'public', 'private'
    AS $$
declare
  v_role text := coalesce(auth.role(), '');
  v_row private.notification_outbox%rowtype;
begin
  if v_role <> 'service_role' then
    raise exception 'service_role required' using errcode='42501';
  end if;
  if p_provider_message_id is null or btrim(p_provider_message_id) = '' then
    raise exception 'provider_message_id required' using errcode='22023';
  end if;
  select * into v_row
  from private.notification_outbox
  where provider_message_id = p_provider_message_id
    and environment = 'sandbox'
    and adapter_key = 'resend-email-v1'
  order by created_at desc
  limit 1;
  if not found then
    return jsonb_build_object('found',false,'provider_message_id',p_provider_message_id,'environment','sandbox');
  end if;
  return jsonb_build_object('found',true,'provider_message_id',v_row.provider_message_id,'status',v_row.status,'environment',v_row.environment,'adapter_key',v_row.adapter_key);
end;
$$;


ALTER FUNCTION "public"."vl_resend_reconciliation_source_check"("p_provider_message_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."vl_resend_record_sandbox_send"("p_recipient_hash" "text", "p_subject" "text", "p_provider_message_id" "text", "p_idempotency_key" "text", "p_created_by" "uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'private', 'public', 'pg_temp'
    AS $$ declare v private.notification_outbox%rowtype; begin if coalesce(trim(p_recipient_hash),'')='' or coalesce(trim(p_provider_message_id),'')='' or coalesce(trim(p_idempotency_key),'')='' then raise exception 'required evidence missing'; end if; select * into v from private.notification_outbox where adapter_key='resend-email-v1' and environment='sandbox' and idempotency_key=p_idempotency_key for update; if found then if v.provider_message_id is distinct from p_provider_message_id then raise exception 'idempotency conflict'; end if; return jsonb_build_object('ok',true,'duplicate',true,'id',v.id,'provider_message_id',v.provider_message_id,'status',v.status); end if; insert into private.notification_outbox(adapter_key,channel,recipient_hash,subject,provider_message_id,idempotency_key,environment,status,metadata) values('resend-email-v1','email',p_recipient_hash,left(p_subject,200),p_provider_message_id,p_idempotency_key,'sandbox','sent',jsonb_build_object('created_by',p_created_by,'provider','resend','pii_stored',false,'production_send',false)) returning * into v; return jsonb_build_object('ok',true,'duplicate',false,'id',v.id,'provider_message_id',v.provider_message_id,'status',v.status); exception when unique_violation then select * into v from private.notification_outbox where adapter_key='resend-email-v1' and environment='sandbox' and idempotency_key=p_idempotency_key; if v.provider_message_id is distinct from p_provider_message_id then raise exception 'idempotency conflict'; end if; return jsonb_build_object('ok',true,'duplicate',true,'id',v.id,'provider_message_id',v.provider_message_id,'status',v.status); end $$;


ALTER FUNCTION "public"."vl_resend_record_sandbox_send"("p_recipient_hash" "text", "p_subject" "text", "p_provider_message_id" "text", "p_idempotency_key" "text", "p_created_by" "uuid") OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "private"."agent_capability_grants" (
    "grant_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "agent_id" "text" NOT NULL,
    "principal_type" "text" NOT NULL,
    "agent_version" "text",
    "role_name" "text" NOT NULL,
    "capabilities" "text"[] NOT NULL,
    "scope" "jsonb" NOT NULL,
    "budget" "jsonb" DEFAULT '{"max_retries": 0, "timeout_seconds": 300}'::"jsonb" NOT NULL,
    "delegated_from_grant_id" "uuid",
    "valid_from" timestamp with time zone DEFAULT "now"() NOT NULL,
    "valid_until" timestamp with time zone,
    "revoked_at" timestamp with time zone,
    "revocation_reason" "text",
    "created_by" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "agent_capability_grants_budget_check" CHECK (("jsonb_typeof"("budget") = 'object'::"text")),
    CONSTRAINT "agent_capability_grants_capabilities_check" CHECK (("cardinality"("capabilities") > 0)),
    CONSTRAINT "agent_capability_grants_check" CHECK ((("valid_until" IS NULL) OR ("valid_until" > "valid_from"))),
    CONSTRAINT "agent_capability_grants_check1" CHECK ((("revoked_at" IS NULL) OR ("revoked_at" >= "created_at"))),
    CONSTRAINT "agent_capability_grants_check2" CHECK ((("principal_type" <> 'agent'::"text") OR ("agent_version" IS NOT NULL))),
    CONSTRAINT "agent_capability_grants_check3" CHECK ((("principal_type" <> 'agent'::"text") OR (NOT ("capabilities" && ARRAY['production.approve'::"text", 'production.promote'::"text"])))),
    CONSTRAINT "agent_capability_grants_principal_type_check" CHECK (("principal_type" = ANY (ARRAY['agent'::"text", 'human'::"text", 'system'::"text"]))),
    CONSTRAINT "agent_capability_grants_scope_check" CHECK ((("jsonb_typeof"("scope") = 'object'::"text") AND ("scope" <> '{}'::"jsonb")))
);


ALTER TABLE "private"."agent_capability_grants" OWNER TO "postgres";


COMMENT ON TABLE "private"."agent_capability_grants" IS 'Authoritative ACP grants with DB-level monotonic delegation validation. Worker agents cannot grant or widen their own authority.';



CREATE TABLE IF NOT EXISTS "private"."agent_control_audit_events" (
    "event_id" "text" NOT NULL,
    "schema_version" "text" DEFAULT '1.0'::"text" NOT NULL,
    "action_id" "text" NOT NULL,
    "event_seq" integer NOT NULL,
    "event_type" "text" NOT NULL,
    "recorded_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "requester" "jsonb" NOT NULL,
    "delegator_chain" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "capability" "text" NOT NULL,
    "scope" "jsonb" NOT NULL,
    "input_digest" "text" NOT NULL,
    "decision" "text",
    "reason_code" "text",
    "execution_status" "text",
    "result_digest" "text",
    "previous_event_digest" "text",
    "event_digest" "text" NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "agent_control_audit_events_action_id_check" CHECK ((("length"("action_id") >= 16) AND ("length"("action_id") <= 200))),
    CONSTRAINT "agent_control_audit_events_decision_check" CHECK ((("decision" IS NULL) OR ("decision" = ANY (ARRAY['allow'::"text", 'deny'::"text", 'require_human_approval'::"text"])))),
    CONSTRAINT "agent_control_audit_events_delegator_chain_check" CHECK (("jsonb_typeof"("delegator_chain") = 'array'::"text")),
    CONSTRAINT "agent_control_audit_events_event_digest_check" CHECK (("event_digest" ~ '^sha256:[a-f0-9]{64}$'::"text")),
    CONSTRAINT "agent_control_audit_events_event_id_check" CHECK ((("length"("event_id") >= 16) AND ("length"("event_id") <= 200))),
    CONSTRAINT "agent_control_audit_events_event_seq_check" CHECK (("event_seq" > 0)),
    CONSTRAINT "agent_control_audit_events_event_type_check" CHECK (("event_type" = ANY (ARRAY['action_requested'::"text", 'policy_decided'::"text", 'execution_started'::"text", 'execution_completed'::"text", 'execution_failed'::"text", 'delegation_recorded'::"text", 'idempotent_replay'::"text"]))),
    CONSTRAINT "agent_control_audit_events_execution_status_check" CHECK ((("execution_status" IS NULL) OR ("execution_status" = ANY (ARRAY['not_started'::"text", 'running'::"text", 'succeeded'::"text", 'failed'::"text", 'blocked'::"text"])))),
    CONSTRAINT "agent_control_audit_events_input_digest_check" CHECK (("input_digest" ~ '^sha256:[a-f0-9]{64}$'::"text")),
    CONSTRAINT "agent_control_audit_events_metadata_check" CHECK (("jsonb_typeof"("metadata") = 'object'::"text")),
    CONSTRAINT "agent_control_audit_events_previous_event_digest_check" CHECK ((("previous_event_digest" IS NULL) OR ("previous_event_digest" ~ '^sha256:[a-f0-9]{64}$'::"text"))),
    CONSTRAINT "agent_control_audit_events_requester_check" CHECK ((("jsonb_typeof"("requester") = 'object'::"text") AND ("requester" ? 'agent_id'::"text") AND ("requester" ? 'agent_version'::"text") AND ("requester" ? 'role'::"text") AND ("requester" ? 'principal_type'::"text"))),
    CONSTRAINT "agent_control_audit_events_result_digest_check" CHECK ((("result_digest" IS NULL) OR ("result_digest" ~ '^sha256:[a-f0-9]{64}$'::"text"))),
    CONSTRAINT "agent_control_audit_events_schema_version_check" CHECK (("schema_version" = '1.0'::"text")),
    CONSTRAINT "agent_control_audit_events_scope_check" CHECK ((("jsonb_typeof"("scope") = 'object'::"text") AND ("scope" <> '{}'::"jsonb")))
);


ALTER TABLE "private"."agent_control_audit_events" OWNER TO "postgres";


COMMENT ON TABLE "private"."agent_control_audit_events" IS 'Append-only ACP audit evidence aligned with audit-event.schema.json. Sequence and previous digest are DB-validated.';



CREATE TABLE IF NOT EXISTS "private"."app_compiler_audit" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "prompt" "text" NOT NULL,
    "inferred_builder_type" "text",
    "inferred_target" "text",
    "inferred_capabilities" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "routing_result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "compiled_spec" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "private"."app_compiler_audit" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."app_launch_audit" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "app_spec_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "approver_id" "uuid" NOT NULL,
    "builder_key" "text" NOT NULL,
    "workflow_id" "uuid",
    "factory_run_id" "uuid",
    "decision" "text" NOT NULL,
    "details" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "private"."app_launch_audit" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."assisted_build_cost_policy" (
    "complexity_class" "text" NOT NULL,
    "factory_credit_estimate" integer NOT NULL,
    "service_tier" "text" NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "assisted_build_cost_policy_complexity_class_check" CHECK (("complexity_class" = ANY (ARRAY['low'::"text", 'medium'::"text", 'high'::"text"]))),
    CONSTRAINT "assisted_build_cost_policy_factory_credit_estimate_check" CHECK ((("factory_credit_estimate" > 0) AND ("factory_credit_estimate" <= 100)))
);


ALTER TABLE "private"."assisted_build_cost_policy" OWNER TO "postgres";


CREATE OR REPLACE VIEW "private"."assisted_build_quote_catalog" WITH ("security_barrier"='true', "security_invoker"='false') AS
 SELECT "complexity_class",
    "jsonb_build_object"('complexity_class', "complexity_class", 'factory_credit_estimate', "factory_credit_estimate", 'service_tier_recommendation', "service_tier", 'pricing_source', 'private.assisted_build_cost_policy', 'commercial_amount', NULL::"unknown", 'production_payment_performed', false) AS "quote"
   FROM "private"."assisted_build_cost_policy" "policy"
  WHERE (("enabled" = true) AND ("auth"."uid"() IS NOT NULL));


ALTER VIEW "private"."assisted_build_quote_catalog" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."builder_certification_golden_profiles" (
    "builder_key" "text" NOT NULL,
    "project_name" "text" NOT NULL,
    "app_spec_title" "text",
    "target_platforms" "text"[] NOT NULL,
    "max_batch_runs" integer DEFAULT 2 NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "builder_certification_golden_profiles_max_batch_runs_check" CHECK ((("max_batch_runs" >= 1) AND ("max_batch_runs" <= 2)))
);


ALTER TABLE "private"."builder_certification_golden_profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."builder_release_gate_profiles" (
    "builder_key" "text" NOT NULL,
    "required_gates" "jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "policy_version" integer DEFAULT 1 NOT NULL,
    "policy_sha256" "text" NOT NULL,
    CONSTRAINT "builder_release_gate_profiles_policy_sha256_chk" CHECK (("policy_sha256" ~ '^[0-9a-f]{64}$'::"text")),
    CONSTRAINT "builder_release_gate_profiles_policy_version_check" CHECK (("policy_version" > 0)),
    CONSTRAINT "builder_release_gate_profiles_required_gates_array" CHECK (("jsonb_typeof"("required_gates") = 'array'::"text"))
);


ALTER TABLE "private"."builder_release_gate_profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."builder_route_decisions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "requested_builder_type" "text",
    "requested_target" "text",
    "required_capabilities" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "selected_builder_key" "text",
    "candidate_count" integer DEFAULT 0 NOT NULL,
    "decision" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "private"."builder_route_decisions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."capability_adapter_evidence" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "evidence_type" "text" NOT NULL,
    "evidence_status" "text" NOT NULL,
    "source_factory_run_id" "uuid",
    "source_project_id" "uuid",
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "capability_adapter_evidence_evidence_status_check" CHECK (("evidence_status" = ANY (ARRAY['pass'::"text", 'fail'::"text", 'pending'::"text"])))
);


ALTER TABLE "private"."capability_adapter_evidence" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."capability_adapter_registry" (
    "adapter_key" "text" NOT NULL,
    "adapter_type" "text" NOT NULL,
    "provider" "text" NOT NULL,
    "version" "text" NOT NULL,
    "status" "text" DEFAULT 'experimental'::"text" NOT NULL,
    "capabilities" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "required_gates" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "configuration" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "capability_adapter_registry_adapter_type_check" CHECK (("adapter_type" = ANY (ARRAY['auth'::"text", 'storage'::"text", 'payment'::"text", 'notification'::"text", 'database'::"text"]))),
    CONSTRAINT "capability_adapter_registry_status_check" CHECK (("status" = ANY (ARRAY['experimental'::"text", 'candidate'::"text", 'active'::"text", 'disabled'::"text"])))
);


ALTER TABLE "private"."capability_adapter_registry" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."capability_adapter_results" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "decision" "text" NOT NULL,
    "score" numeric DEFAULT 0 NOT NULL,
    "passed_gates" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "missing_gates" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "evaluated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "capability_adapter_results_decision_check" CHECK (("decision" = ANY (ARRAY['not_ready'::"text", 'candidate'::"text", 'certified'::"text"]))),
    CONSTRAINT "capability_adapter_results_score_check" CHECK ((("score" >= (0)::numeric) AND ("score" <= (1)::numeric)))
);


ALTER TABLE "private"."capability_adapter_results" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."factory_execution_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "event_type" "text" NOT NULL,
    "from_state" "text",
    "to_state" "text",
    "payload" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "private"."factory_execution_events" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."internal_usage_audit" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid",
    "project_id" "uuid" NOT NULL,
    "actor_user_id" "uuid" NOT NULL,
    "event_type" "text" NOT NULL,
    "reason" "text",
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "recorded_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "private"."internal_usage_audit" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."internal_usage_ledger" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "requested_by" "uuid" NOT NULL,
    "classification" "text" NOT NULL,
    "estimated_cost_units" bigint NOT NULL,
    "actual_cost_units" bigint,
    "override_id" "uuid",
    "recorded_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "internal_usage_ledger_actual_cost_units_check" CHECK ((("actual_cost_units" IS NULL) OR ("actual_cost_units" >= 0))),
    CONSTRAINT "internal_usage_ledger_classification_check" CHECK (("classification" = ANY (ARRAY['r_and_d'::"text", 'vl_maintenance'::"text", 'demo'::"text", 'customer_poc'::"text", 'internal_commercial_project'::"text"]))),
    CONSTRAINT "internal_usage_ledger_estimated_cost_units_check" CHECK (("estimated_cost_units" >= 0))
);


ALTER TABLE "private"."internal_usage_ledger" OWNER TO "postgres";


CREATE OR REPLACE VIEW "private"."internal_usage_override_request" WITH ("security_barrier"='true', "security_invoker"='true') AS
 SELECT NULL::"uuid" AS "project_id",
    NULL::"text" AS "reason",
    NULL::integer AS "duration_minutes",
    NULL::"jsonb" AS "result"
  WHERE false;


ALTER VIEW "private"."internal_usage_override_request" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."internal_usage_overrides" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "requested_by" "uuid" NOT NULL,
    "reason" "text" NOT NULL,
    "valid_from" timestamp with time zone DEFAULT "now"() NOT NULL,
    "expires_at" timestamp with time zone NOT NULL,
    "revoked_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "internal_usage_overrides_check" CHECK (("expires_at" > "valid_from")),
    CONSTRAINT "internal_usage_overrides_check1" CHECK (("expires_at" <= ("valid_from" + '04:00:00'::interval))),
    CONSTRAINT "internal_usage_overrides_reason_check" CHECK (("length"("btrim"("reason")) >= 12))
);


ALTER TABLE "private"."internal_usage_overrides" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."internal_usage_policy" (
    "singleton" boolean DEFAULT true NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    "daily_run_limit" integer NOT NULL,
    "concurrent_run_limit" integer NOT NULL,
    "daily_estimated_cost_unit_limit" bigint NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "internal_usage_policy_concurrent_run_limit_check" CHECK (("concurrent_run_limit" > 0)),
    CONSTRAINT "internal_usage_policy_daily_estimated_cost_unit_limit_check" CHECK (("daily_estimated_cost_unit_limit" > 0)),
    CONSTRAINT "internal_usage_policy_daily_run_limit_check" CHECK (("daily_run_limit" > 0)),
    CONSTRAINT "internal_usage_policy_singleton_check" CHECK ("singleton")
);


ALTER TABLE "private"."internal_usage_policy" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."launch_readiness_checks" (
    "check_key" "text" NOT NULL,
    "category" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "blocking" boolean DEFAULT true NOT NULL,
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "checked_at" timestamp with time zone,
    "required_for_pilot" boolean DEFAULT true NOT NULL,
    CONSTRAINT "launch_readiness_checks_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'pass'::"text", 'fail'::"text", 'blocked'::"text", 'not_applicable'::"text"])))
);


ALTER TABLE "private"."launch_readiness_checks" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."notification_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "provider_message_id" "text",
    "event_key" "text" NOT NULL,
    "event_type" "text" NOT NULL,
    "signature_valid" boolean NOT NULL,
    "payload_sha256" "text" NOT NULL,
    "duplicate" boolean DEFAULT false NOT NULL,
    "applied" boolean DEFAULT false NOT NULL,
    "received_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "processed_at" timestamp with time zone,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL
);


ALTER TABLE "private"."notification_events" OWNER TO "postgres";


COMMENT ON TABLE "private"."notification_events" IS 'VL sanitized notification delivery event ledger for signed webhook and idempotency evidence.';



CREATE TABLE IF NOT EXISTS "private"."notification_outbox" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "channel" "text" NOT NULL,
    "recipient_hash" "text" NOT NULL,
    "template_key" "text",
    "subject" "text",
    "provider_message_id" "text",
    "idempotency_key" "text" NOT NULL,
    "environment" "text" DEFAULT 'sandbox'::"text" NOT NULL,
    "status" "text" DEFAULT 'queued'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "notification_outbox_channel_check" CHECK (("channel" = 'email'::"text")),
    CONSTRAINT "notification_outbox_environment_check" CHECK (("environment" = ANY (ARRAY['sandbox'::"text", 'development'::"text", 'staging'::"text"]))),
    CONSTRAINT "notification_outbox_status_check" CHECK (("status" = ANY (ARRAY['queued'::"text", 'sent'::"text", 'delivered'::"text", 'bounced'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "private"."notification_outbox" OWNER TO "postgres";


COMMENT ON TABLE "private"."notification_outbox" IS 'VL notification outbox; stores hashed recipients and provider message ids, not provider secrets.';



CREATE TABLE IF NOT EXISTS "private"."notification_production_activations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "requested_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "approved_at" timestamp with time zone,
    "approved_by" "uuid",
    "rationale" "text",
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "notification_production_activations_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'approved'::"text", 'revoked'::"text"])))
);


ALTER TABLE "private"."notification_production_activations" OWNER TO "postgres";


COMMENT ON TABLE "private"."notification_production_activations" IS 'Private fail-closed notification activation ledger. RLS enabled; direct access is service-role/postgres only.';



CREATE TABLE IF NOT EXISTS "private"."notification_reconciliation_checks" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "outbox_id" "uuid" NOT NULL,
    "expected_status" "text" NOT NULL,
    "provider_status" "text",
    "status" "text" NOT NULL,
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "checked_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "notification_reconciliation_checks_status_check" CHECK (("status" = ANY (ARRAY['pass'::"text", 'fail'::"text", 'blocked'::"text"])))
);


ALTER TABLE "private"."notification_reconciliation_checks" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."operational_incidents" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "incident_key" "text" NOT NULL,
    "severity" "text" NOT NULL,
    "status" "text" DEFAULT 'open'::"text" NOT NULL,
    "summary" "text" NOT NULL,
    "started_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "resolved_at" timestamp with time zone,
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "alert_state" "text" DEFAULT 'pending'::"text" NOT NULL,
    "alert_attempts" integer DEFAULT 0 NOT NULL,
    "alert_lease_token" "uuid",
    "alert_leased_at" timestamp with time zone,
    "alert_sent_at" timestamp with time zone,
    "alert_error_text" "text",
    CONSTRAINT "operational_incidents_alert_attempts_check" CHECK (("alert_attempts" >= 0)),
    CONSTRAINT "operational_incidents_alert_state_check" CHECK (("alert_state" = ANY (ARRAY['pending'::"text", 'leased'::"text", 'sent'::"text", 'failed'::"text"]))),
    CONSTRAINT "operational_incidents_severity_check" CHECK (("severity" = ANY (ARRAY['sev1'::"text", 'sev2'::"text", 'sev3'::"text", 'sev4'::"text"]))),
    CONSTRAINT "operational_incidents_status_check" CHECK (("status" = ANY (ARRAY['open'::"text", 'mitigating'::"text", 'resolved'::"text"])))
);


ALTER TABLE "private"."operational_incidents" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."payment_fulfillment_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "adapter_key" "text" DEFAULT 'billplz-payment-v1'::"text" NOT NULL,
    "action_key" "text" NOT NULL,
    "status" "text" NOT NULL,
    "reason" "text",
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "payment_fulfillment_events_status_check" CHECK (("status" = ANY (ARRAY['fulfilled'::"text", 'rejected'::"text"])))
);


ALTER TABLE "private"."payment_fulfillment_events" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."payment_production_fulfillment_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "action_key" "text" NOT NULL,
    "status" "text" NOT NULL,
    "reason" "text",
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "payment_production_fulfillment_events_status_check" CHECK (("status" = ANY (ARRAY['fulfilled'::"text", 'blocked'::"text"])))
);


ALTER TABLE "private"."payment_production_fulfillment_events" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."payment_production_orders" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" DEFAULT 'billplz-payment-v1'::"text" NOT NULL,
    "provider_bill_id" "text",
    "merchant_reference" "text" NOT NULL,
    "amount_minor" integer NOT NULL,
    "currency" "text" DEFAULT 'MYR'::"text" NOT NULL,
    "environment" "text" DEFAULT 'production'::"text" NOT NULL,
    "purpose" "text" DEFAULT 'controlled_live_test'::"text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "fulfillment_state" "text" DEFAULT 'unfulfilled'::"text" NOT NULL,
    "checkout_url" "text",
    "created_by" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "paid_at" timestamp with time zone,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "payment_production_orders_amount_minor_check" CHECK (("amount_minor" > 0)),
    CONSTRAINT "payment_production_orders_currency_check" CHECK (("currency" = 'MYR'::"text")),
    CONSTRAINT "payment_production_orders_environment_check" CHECK (("environment" = 'production'::"text")),
    CONSTRAINT "payment_production_orders_fulfillment_state_check" CHECK (("fulfillment_state" = ANY (ARRAY['unfulfilled'::"text", 'fulfilled'::"text", 'blocked'::"text", 'reversed'::"text"]))),
    CONSTRAINT "payment_production_orders_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'paid'::"text", 'cancelled'::"text", 'failed'::"text", 'refunded'::"text"])))
);


ALTER TABLE "private"."payment_production_orders" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."payment_production_webhook_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "event_key" "text" NOT NULL,
    "provider_bill_id" "text",
    "payload_sha256" "text" NOT NULL,
    "signature_valid" boolean NOT NULL,
    "normalized_status" "text",
    "amount_minor" integer,
    "applied" boolean DEFAULT false NOT NULL,
    "duplicate" boolean DEFAULT false NOT NULL,
    "error_text" "text",
    "received_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "processed_at" timestamp with time zone,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL
);


ALTER TABLE "private"."payment_production_webhook_events" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."payment_reconciliation_checks" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "order_id" "uuid" NOT NULL,
    "provider_bill_id" "text",
    "expected_status" "text" NOT NULL,
    "provider_status" "text",
    "expected_amount_minor" integer NOT NULL,
    "provider_amount_minor" integer,
    "status" "text" NOT NULL,
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "checked_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "payment_reconciliation_checks_status_check" CHECK (("status" = ANY (ARRAY['pass'::"text", 'fail'::"text", 'blocked'::"text"])))
);


ALTER TABLE "private"."payment_reconciliation_checks" OWNER TO "postgres";


COMMENT ON TABLE "private"."payment_reconciliation_checks" IS 'VL sandbox payment reconciliation evidence.';



CREATE TABLE IF NOT EXISTS "private"."payment_sandbox_orders" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "provider_bill_id" "text",
    "merchant_reference" "text" NOT NULL,
    "amount_minor" integer NOT NULL,
    "currency" "text" DEFAULT 'MYR'::"text" NOT NULL,
    "environment" "text" DEFAULT 'sandbox'::"text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "fulfillment_state" "text" DEFAULT 'unfulfilled'::"text" NOT NULL,
    "checkout_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "paid_at" timestamp with time zone,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "payment_sandbox_orders_amount_minor_check" CHECK (("amount_minor" > 0)),
    CONSTRAINT "payment_sandbox_orders_currency_check" CHECK (("currency" = 'MYR'::"text")),
    CONSTRAINT "payment_sandbox_orders_environment_check" CHECK (("environment" = 'sandbox'::"text")),
    CONSTRAINT "payment_sandbox_orders_fulfillment_state_check" CHECK (("fulfillment_state" = ANY (ARRAY['unfulfilled'::"text", 'fulfilled'::"text", 'reversed'::"text"]))),
    CONSTRAINT "payment_sandbox_orders_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'paid'::"text", 'failed'::"text", 'cancelled'::"text", 'refunded'::"text"])))
);


ALTER TABLE "private"."payment_sandbox_orders" OWNER TO "postgres";


COMMENT ON TABLE "private"."payment_sandbox_orders" IS 'VL sandbox-only payment orders. Never stores provider credentials.';



CREATE TABLE IF NOT EXISTS "private"."payment_webhook_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "adapter_key" "text" NOT NULL,
    "event_key" "text" NOT NULL,
    "provider_bill_id" "text",
    "payload_sha256" "text" NOT NULL,
    "signature_valid" boolean NOT NULL,
    "normalized_status" "text",
    "amount_minor" integer,
    "applied" boolean DEFAULT false NOT NULL,
    "duplicate" boolean DEFAULT false NOT NULL,
    "error_text" "text",
    "received_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "processed_at" timestamp with time zone,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "payment_webhook_events_normalized_status_check" CHECK (("normalized_status" = ANY (ARRAY['pending'::"text", 'paid'::"text", 'failed'::"text", 'cancelled'::"text", 'refunded'::"text"])))
);


ALTER TABLE "private"."payment_webhook_events" OWNER TO "postgres";


COMMENT ON TABLE "private"."payment_webhook_events" IS 'VL sanitized payment webhook ledger for idempotency and audit. No raw secrets or full PII payloads.';



CREATE TABLE IF NOT EXISTS "private"."product_alignment_policy" (
    "policy_key" "text" NOT NULL,
    "contract_version" "text" NOT NULL,
    "activated_at" timestamp with time zone NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    CONSTRAINT "product_alignment_policy_key" CHECK (("policy_key" = 'default'::"text"))
);


ALTER TABLE "private"."product_alignment_policy" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."production_adapter_registry" (
    "adapter_key" "text" NOT NULL,
    "target_kind" "text" NOT NULL,
    "status" "text" NOT NULL,
    "capabilities" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "notes" "text",
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "builder_key" "text" NOT NULL,
    "configured" boolean DEFAULT false NOT NULL,
    "target_type" "text" NOT NULL,
    "required_credentials" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "can_deploy" boolean DEFAULT false NOT NULL,
    "can_rollback" boolean DEFAULT false NOT NULL,
    "can_health_check" boolean DEFAULT false NOT NULL,
    "configuration" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "production_adapter_registry_status_check" CHECK (("status" = ANY (ARRAY['active'::"text", 'experimental'::"text", 'unavailable'::"text", 'disabled'::"text"])))
);


ALTER TABLE "private"."production_adapter_registry" OWNER TO "postgres";


COMMENT ON TABLE "private"."production_adapter_registry" IS 'Fail-closed production adapter capabilities and configuration state.';



CREATE TABLE IF NOT EXISTS "private"."production_deployment_verifications" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "deployment_id" "uuid" NOT NULL,
    "promotion_job_id" "uuid" NOT NULL,
    "check_key" "text" NOT NULL,
    "expected" "jsonb" NOT NULL,
    "actual" "jsonb" NOT NULL,
    "status" "text" NOT NULL,
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "checked_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "production_deployment_verifications_status_check" CHECK (("status" = ANY (ARRAY['pass'::"text", 'fail'::"text"])))
);


ALTER TABLE "private"."production_deployment_verifications" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."production_promotion_jobs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "deployment_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "builder_key" "text" NOT NULL,
    "artifact_sha256" "text" NOT NULL,
    "state" "text" DEFAULT 'queued'::"text" NOT NULL,
    "attempts" integer DEFAULT 0 NOT NULL,
    "max_attempts" integer DEFAULT 3 NOT NULL,
    "target_adapter" "text",
    "lease_token" "uuid",
    "leased_at" timestamp with time zone,
    "lease_expires_at" timestamp with time zone,
    "result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "error_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "finished_at" timestamp with time zone,
    CONSTRAINT "production_promotion_jobs_state_check" CHECK (("state" = ANY (ARRAY['queued'::"text", 'leased'::"text", 'blocked'::"text", 'succeeded'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "private"."production_promotion_jobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."production_rollback_audits" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "deployment_id" "uuid" NOT NULL,
    "previous_deployment_id" "uuid",
    "requested_by" "uuid",
    "state" "text" NOT NULL,
    "target_adapter" "text",
    "provider_deployment_id" "text",
    "artifact_sha256" "text",
    "reason" "text",
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "requested_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "finished_at" timestamp with time zone,
    "attempts" integer DEFAULT 0 NOT NULL,
    "max_attempts" integer DEFAULT 3 NOT NULL,
    "lease_token" "uuid",
    "leased_at" timestamp with time zone,
    "lease_expires_at" timestamp with time zone,
    "result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "error_text" "text",
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "production_rollback_audits_state_check" CHECK (("state" = ANY (ARRAY['blocked'::"text", 'pending'::"text", 'leased'::"text", 'executing'::"text", 'succeeded'::"text", 'failed'::"text"])))
);


ALTER TABLE "private"."production_rollback_audits" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."release_validation_jobs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "deployment_id" "uuid" NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "builder_key" "text" NOT NULL,
    "state" "text" DEFAULT 'queued'::"text" NOT NULL,
    "attempts" integer DEFAULT 0 NOT NULL,
    "max_attempts" integer DEFAULT 3 NOT NULL,
    "lease_token" "uuid",
    "leased_at" timestamp with time zone,
    "lease_expires_at" timestamp with time zone,
    "runner_identity" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "error_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "finished_at" timestamp with time zone,
    CONSTRAINT "release_validation_jobs_state_check" CHECK (("state" = ANY (ARRAY['queued'::"text", 'leased'::"text", 'succeeded'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "private"."release_validation_jobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."runner_jobs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "builder_key" "text" NOT NULL,
    "state" "text" DEFAULT 'queued'::"text" NOT NULL,
    "attempts" integer DEFAULT 0 NOT NULL,
    "max_attempts" integer DEFAULT 3 NOT NULL,
    "lease_token" "uuid",
    "leased_at" timestamp with time zone,
    "lease_expires_at" timestamp with time zone,
    "runner_identity" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "error_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "finished_at" timestamp with time zone,
    CONSTRAINT "runner_jobs_state_check" CHECK (("state" = ANY (ARRAY['queued'::"text", 'leased'::"text", 'succeeded'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "private"."runner_jobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "private"."usage_counters" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "customer_account_id" "uuid" NOT NULL,
    "metric_key" "text" NOT NULL,
    "window_start" timestamp with time zone NOT NULL,
    "window_end" timestamp with time zone NOT NULL,
    "used_count" bigint DEFAULT 0 NOT NULL,
    "limit_count" bigint NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "usage_counters_limit_count_check" CHECK (("limit_count" >= 0)),
    CONSTRAINT "usage_counters_used_count_check" CHECK (("used_count" >= 0))
);


ALTER TABLE "private"."usage_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."app_specs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "version" integer DEFAULT 1 NOT NULL,
    "title" "text" NOT NULL,
    "objective" "text",
    "spec" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "status" "text" DEFAULT 'draft'::"text" NOT NULL,
    "created_by" "uuid" NOT NULL,
    "approved_by" "uuid",
    "approved_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "software_kind" "text" DEFAULT 'saas'::"text" NOT NULL,
    "target_platforms" "text"[] DEFAULT ARRAY['web'::"text"] NOT NULL,
    "parent_app_spec_id" "uuid",
    "change_request" "text",
    CONSTRAINT "app_specs_software_kind_check" CHECK (("software_kind" = ANY (ARRAY['saas'::"text", 'web_app'::"text", 'pwa'::"text", 'mobile_app'::"text", 'desktop_app'::"text", 'gis_app'::"text", 'ai_app'::"text", 'api_service'::"text", 'internal_tool'::"text"]))),
    CONSTRAINT "app_specs_status_check" CHECK (("status" = ANY (ARRAY['draft'::"text", 'approved'::"text", 'superseded'::"text", 'rejected'::"text"]))),
    CONSTRAINT "app_specs_target_platforms_check" CHECK ((("target_platforms" <@ ARRAY['web'::"text", 'pwa'::"text", 'android'::"text", 'ios'::"text", 'windows'::"text", 'macos'::"text", 'linux'::"text", 'gis'::"text", 'ai'::"text", 'api'::"text"]) AND ("cardinality"("target_platforms") >= 1)))
);


ALTER TABLE "public"."app_specs" OWNER TO "postgres";


COMMENT ON TABLE "public"."app_specs" IS 'Versioned human/AI-approved application specification.';



CREATE TABLE IF NOT EXISTS "public"."approvals" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "workflow_id" "uuid",
    "approval_type" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "requested_by" "uuid" NOT NULL,
    "decided_by" "uuid",
    "rationale" "text",
    "requested_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "decided_at" timestamp with time zone,
    "factory_run_id" "uuid" NOT NULL,
    CONSTRAINT "approvals_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'approved'::"text", 'rejected'::"text", 'expired'::"text"])))
);


ALTER TABLE "public"."approvals" OWNER TO "postgres";


COMMENT ON TABLE "public"."approvals" IS 'Human approval gates for consequential actions.';



CREATE TABLE IF NOT EXISTS "public"."audit_logs" (
    "id" bigint NOT NULL,
    "organization_id" "uuid",
    "project_id" "uuid",
    "actor_user_id" "uuid",
    "action" "text" NOT NULL,
    "entity_type" "text",
    "entity_id" "text",
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."audit_logs" OWNER TO "postgres";


COMMENT ON TABLE "public"."audit_logs" IS 'Append-only user-visible audit trail.';



ALTER TABLE "public"."audit_logs" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."audit_logs_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."build_failure_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "build_step_id" "uuid",
    "builder_key" "text",
    "failure_class" "text" NOT NULL,
    "signature" "text" NOT NULL,
    "error_text" "text" NOT NULL,
    "source" "text" DEFAULT 'worker'::"text" NOT NULL,
    "retryable" boolean DEFAULT false NOT NULL,
    "repair_recipe_key" "text",
    "repair_applied" boolean DEFAULT false NOT NULL,
    "repair_result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."build_failure_events" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."build_steps" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "step_order" integer NOT NULL,
    "step_key" "text" NOT NULL,
    "step_type" "text" NOT NULL,
    "state" "text" DEFAULT 'queued'::"text" NOT NULL,
    "depends_on" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "input" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "output" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "error_text" "text",
    "started_at" timestamp with time zone,
    "finished_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "attempt_count" integer DEFAULT 0 NOT NULL,
    "max_attempts" integer DEFAULT 3 NOT NULL,
    "last_attempt_at" timestamp with time zone,
    CONSTRAINT "build_steps_attempt_count_check" CHECK ((("attempt_count" >= 0) AND (("max_attempts" >= 1) AND ("max_attempts" <= 10)) AND ("attempt_count" <= "max_attempts"))),
    CONSTRAINT "build_steps_state_check" CHECK (("state" = ANY (ARRAY['queued'::"text", 'running'::"text", 'succeeded'::"text", 'failed'::"text", 'blocked'::"text", 'cancelled'::"text"]))),
    CONSTRAINT "build_steps_step_type_check" CHECK (("step_type" = ANY (ARRAY['plan'::"text", 'generate'::"text", 'migrate'::"text", 'configure'::"text", 'test'::"text", 'validate'::"text", 'package'::"text", 'certify'::"text", 'approval'::"text"])))
);


ALTER TABLE "public"."build_steps" OWNER TO "postgres";


COMMENT ON TABLE "public"."build_steps" IS 'Ordered dependency-aware execution steps for a VRS factory run.';



COMMENT ON COLUMN "public"."build_steps"."attempt_count" IS 'Number of worker execution attempts for this step.';



COMMENT ON COLUMN "public"."build_steps"."max_attempts" IS 'Maximum retry attempts allowed before permanent failure.';



CREATE TABLE IF NOT EXISTS "public"."builder_certification_evidence" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "builder_key" "text" NOT NULL,
    "factory_run_id" "uuid",
    "project_id" "uuid",
    "evidence_type" "text" NOT NULL,
    "evidence_status" "text" NOT NULL,
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "source_uri" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "builder_certification_evidence_evidence_status_check" CHECK (("evidence_status" = ANY (ARRAY['pass'::"text", 'fail'::"text", 'pending'::"text"])))
);


ALTER TABLE "public"."builder_certification_evidence" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."builder_certification_policies" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "builder_key" "text" NOT NULL,
    "required_evidence" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "minimum_score" numeric DEFAULT 1.0 NOT NULL,
    "minimum_distinct_runs" integer DEFAULT 1 NOT NULL,
    "allow_auto_activate" boolean DEFAULT true NOT NULL,
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "builder_certification_policies_minimum_distinct_runs_check" CHECK (("minimum_distinct_runs" >= 1)),
    CONSTRAINT "builder_certification_policies_minimum_score_check" CHECK ((("minimum_score" >= (0)::numeric) AND ("minimum_score" <= (1)::numeric))),
    CONSTRAINT "builder_certification_policies_status_check" CHECK (("status" = ANY (ARRAY['active'::"text", 'paused'::"text"])))
);


ALTER TABLE "public"."builder_certification_policies" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."builder_certification_results" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "builder_key" "text" NOT NULL,
    "decision" "text" NOT NULL,
    "score" numeric DEFAULT 0 NOT NULL,
    "passed_evidence" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "missing_evidence" "text"[] DEFAULT '{}'::"text"[] NOT NULL,
    "distinct_run_count" integer DEFAULT 0 NOT NULL,
    "evaluated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    CONSTRAINT "builder_certification_results_decision_check" CHECK (("decision" = ANY (ARRAY['not_ready'::"text", 'candidate'::"text", 'certified'::"text"]))),
    CONSTRAINT "builder_certification_results_score_check" CHECK ((("score" >= (0)::numeric) AND ("score" <= (1)::numeric)))
);


ALTER TABLE "public"."builder_certification_results" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."builder_registry" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "builder_key" "text" NOT NULL,
    "builder_type" "text" NOT NULL,
    "runtime" "text" NOT NULL,
    "targets" "text"[] NOT NULL,
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "capabilities" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "builder_version" integer DEFAULT 1 NOT NULL,
    "version" integer DEFAULT 1 NOT NULL,
    CONSTRAINT "builder_registry_builder_type_check" CHECK (("builder_type" = ANY (ARRAY['web'::"text", 'pwa'::"text", 'mobile'::"text", 'desktop'::"text", 'gis'::"text", 'ai'::"text", 'api'::"text"]))),
    CONSTRAINT "builder_registry_builder_version_check" CHECK (("builder_version" > 0)),
    CONSTRAINT "builder_registry_status_check" CHECK (("status" = ANY (ARRAY['active'::"text", 'experimental'::"text", 'disabled'::"text"])))
);


ALTER TABLE "public"."builder_registry" OWNER TO "postgres";


COMMENT ON TABLE "public"."builder_registry" IS 'VRS Software Factory builder catalogue for web, PWA, mobile, desktop, GIS, AI and API targets.';



COMMENT ON COLUMN "public"."builder_registry"."version" IS 'Immutable logical builder version used in release certification snapshots.';



CREATE OR REPLACE VIEW "public"."capability_adapter_status" WITH ("security_invoker"='true') AS
 SELECT "adapter_key",
    "adapter_type",
    "provider",
    "version",
    "status",
    "capabilities",
    "required_gates",
    "updated_at"
   FROM "private"."capability_adapter_registry";


ALTER VIEW "public"."capability_adapter_status" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."ci_evidence_ingestions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "factory_run_id" "uuid",
    "builder_key" "text" NOT NULL,
    "provider" "text" DEFAULT 'github_actions'::"text" NOT NULL,
    "repository" "text" NOT NULL,
    "external_run_id" "text" NOT NULL,
    "external_job_id" "text",
    "head_sha" "text",
    "run_status" "text" NOT NULL,
    "run_conclusion" "text",
    "step_results" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "artifact_results" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "raw_summary" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "ingested_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."ci_evidence_ingestions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."ci_repair_actions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "factory_run_id" "uuid",
    "builder_key" "text" NOT NULL,
    "failure_event_id" "uuid",
    "recipe_key" "text" NOT NULL,
    "provider" "text" DEFAULT 'github'::"text" NOT NULL,
    "repository" "text" NOT NULL,
    "branch" "text" DEFAULT 'main'::"text" NOT NULL,
    "risk_level" "text" NOT NULL,
    "auto_apply" boolean DEFAULT false NOT NULL,
    "state" "text" DEFAULT 'proposed'::"text" NOT NULL,
    "repair_plan" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "execution_result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "retry_run_id" "text",
    "created_by" "uuid" DEFAULT "auth"."uid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "applied_at" timestamp with time zone,
    "verified_at" timestamp with time zone,
    CONSTRAINT "ci_repair_actions_state_check" CHECK (("state" = ANY (ARRAY['proposed'::"text", 'approved'::"text", 'applying'::"text", 'applied'::"text", 'retrying'::"text", 'verified'::"text", 'failed'::"text", 'rejected'::"text"])))
);


ALTER TABLE "public"."ci_repair_actions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."customer_accounts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "owner_user_id" "uuid" NOT NULL,
    "display_name" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "plan_key" "text" DEFAULT 'launch_pilot'::"text" NOT NULL,
    "onboarding_state" "text" DEFAULT 'started'::"text" NOT NULL,
    "terms_accepted_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "customer_accounts_display_name_check" CHECK ((("length"(TRIM(BOTH FROM "display_name")) >= 2) AND ("length"(TRIM(BOTH FROM "display_name")) <= 120))),
    CONSTRAINT "customer_accounts_onboarding_state_check" CHECK (("onboarding_state" = ANY (ARRAY['started'::"text", 'profile_complete'::"text", 'terms_pending'::"text", 'ready'::"text", 'blocked'::"text"]))),
    CONSTRAINT "customer_accounts_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'active'::"text", 'suspended'::"text", 'closed'::"text"])))
);


ALTER TABLE "public"."customer_accounts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."deployments" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "environment_id" "uuid" NOT NULL,
    "workflow_id" "uuid",
    "release_version" "text" NOT NULL,
    "status" "text" DEFAULT 'planned'::"text" NOT NULL,
    "artifact_sha256" "text",
    "certificate" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_by" "uuid" NOT NULL,
    "approved_by" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "deployed_at" timestamp with time zone,
    "factory_run_id" "uuid" NOT NULL,
    "required_gates_snapshot" "jsonb",
    "builder_key_snapshot" "text",
    "builder_version_snapshot" integer,
    "gate_policy_version_snapshot" integer,
    "gate_policy_sha256" "text",
    "app_spec_sha256" "text",
    "source_commit_sha" "text",
    "builder_profile_sha256_snapshot" "text",
    CONSTRAINT "deployments_app_spec_sha256_chk" CHECK ((("app_spec_sha256" IS NULL) OR ("app_spec_sha256" ~ '^[0-9a-f]{64}$'::"text"))),
    CONSTRAINT "deployments_builder_profile_sha256_chk" CHECK ((("builder_profile_sha256_snapshot" IS NULL) OR ("builder_profile_sha256_snapshot" ~ '^[0-9a-f]{64}$'::"text"))),
    CONSTRAINT "deployments_gate_policy_sha256_chk" CHECK ((("gate_policy_sha256" IS NULL) OR ("gate_policy_sha256" ~ '^[0-9a-f]{64}$'::"text"))),
    CONSTRAINT "deployments_status_check" CHECK (("status" = ANY (ARRAY['planned'::"text", 'certified'::"text", 'approved'::"text", 'deploying'::"text", 'deployed'::"text", 'failed'::"text", 'rolled_back'::"text"])))
);


ALTER TABLE "public"."deployments" OWNER TO "postgres";


COMMENT ON TABLE "public"."deployments" IS 'Release/deployment records; production requires explicit approval.';



CREATE TABLE IF NOT EXISTS "public"."environments" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "name" "text" NOT NULL,
    "kind" "text" NOT NULL,
    "status" "text" DEFAULT 'ready'::"text" NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "environments_kind_check" CHECK (("kind" = ANY (ARRAY['development'::"text", 'staging'::"text", 'production'::"text"]))),
    CONSTRAINT "environments_status_check" CHECK (("status" = ANY (ARRAY['ready'::"text", 'busy'::"text", 'degraded'::"text", 'paused'::"text"])))
);


ALTER TABLE "public"."environments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."factory_artifacts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "artifact_type" "text" NOT NULL,
    "name" "text" NOT NULL,
    "storage_path" "text",
    "sha256" "text",
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "factory_artifacts_artifact_type_check" CHECK (("artifact_type" = ANY (ARRAY['source'::"text", 'migration'::"text", 'edge_function'::"text", 'test_report'::"text", 'release_certificate'::"text", 'bundle'::"text", 'other'::"text"])))
);


ALTER TABLE "public"."factory_artifacts" OWNER TO "postgres";


COMMENT ON TABLE "public"."factory_artifacts" IS 'Immutable references and hashes for generated build artifacts.';



CREATE TABLE IF NOT EXISTS "public"."factory_runs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "app_spec_id" "uuid",
    "workflow_id" "uuid",
    "requested_by" "uuid" NOT NULL,
    "run_type" "text" NOT NULL,
    "state" "text" DEFAULT 'queued'::"text" NOT NULL,
    "target_environment" "text" DEFAULT 'staging'::"text" NOT NULL,
    "production_locked" boolean DEFAULT true NOT NULL,
    "input" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "plan" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "error_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "started_at" timestamp with time zone,
    "finished_at" timestamp with time zone,
    "target_platforms" "text"[] DEFAULT ARRAY['web'::"text"] NOT NULL,
    "base_factory_run_id" "uuid",
    CONSTRAINT "factory_runs_run_type_check" CHECK (("run_type" = ANY (ARRAY['build'::"text", 'repair'::"text", 'upgrade'::"text", 'validate'::"text", 'certify'::"text"]))),
    CONSTRAINT "factory_runs_state_check" CHECK (("state" = ANY (ARRAY['queued'::"text", 'planning'::"text", 'building'::"text", 'validating'::"text", 'awaiting_approval'::"text", 'certified'::"text", 'failed'::"text", 'cancelled'::"text"]))),
    CONSTRAINT "factory_runs_target_environment_check" CHECK (("target_environment" = ANY (ARRAY['development'::"text", 'staging'::"text", 'production'::"text"])))
);


ALTER TABLE "public"."factory_runs" OWNER TO "postgres";


COMMENT ON TABLE "public"."factory_runs" IS 'VRS SaaS Factory execution state machine. Production remains locked until all required gates pass and human approval exists.';



CREATE TABLE IF NOT EXISTS "public"."generated_artifacts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "factory_run_id" "uuid" NOT NULL,
    "project_id" "uuid" NOT NULL,
    "build_step_id" "uuid",
    "artifact_kind" "text" NOT NULL,
    "path" "text" NOT NULL,
    "content" "text" NOT NULL,
    "sha256" "text" NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "generated_artifacts_artifact_kind_check" CHECK (("artifact_kind" = ANY (ARRAY['source'::"text", 'migration'::"text", 'config'::"text", 'test'::"text", 'manifest'::"text", 'report'::"text", 'other'::"text"])))
);


ALTER TABLE "public"."generated_artifacts" OWNER TO "postgres";


COMMENT ON TABLE "public"."generated_artifacts" IS 'Deterministically generated VRS build outputs. No secrets may be stored here.';



CREATE TABLE IF NOT EXISTS "public"."jobs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "workflow_id" "uuid" NOT NULL,
    "job_type" "text" NOT NULL,
    "state" "text" DEFAULT 'queued'::"text" NOT NULL,
    "attempt" integer DEFAULT 0 NOT NULL,
    "payload" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "result" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "error_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "started_at" timestamp with time zone,
    "finished_at" timestamp with time zone,
    CONSTRAINT "jobs_state_check" CHECK (("state" = ANY (ARRAY['queued'::"text", 'running'::"text", 'succeeded'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "public"."jobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."module_registry" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "module_key" "text" NOT NULL,
    "module_type" "text" NOT NULL,
    "version" "text" DEFAULT '0.1.0'::"text" NOT NULL,
    "status" "text" DEFAULT 'planned'::"text" NOT NULL,
    "config" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "artifact_sha256" "text",
    "created_by" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "module_registry_module_type_check" CHECK (("module_type" = ANY (ARRAY['auth'::"text", 'database'::"text", 'storage'::"text", 'edge_function'::"text", 'frontend'::"text", 'integration'::"text", 'billing'::"text", 'reporting'::"text", 'ai'::"text", 'web'::"text", 'pwa'::"text", 'mobile'::"text", 'desktop'::"text", 'gis'::"text", 'api'::"text", 'packaging'::"text", 'offline_sync'::"text", 'other'::"text"]))),
    CONSTRAINT "module_registry_status_check" CHECK (("status" = ANY (ARRAY['planned'::"text", 'generated'::"text", 'validated'::"text", 'active'::"text", 'deprecated'::"text", 'failed'::"text"])))
);


ALTER TABLE "public"."module_registry" OWNER TO "postgres";


COMMENT ON TABLE "public"."module_registry" IS 'Generated/managed modules for each VRS-built SaaS project.';



CREATE TABLE IF NOT EXISTS "public"."organization_members" (
    "organization_id" "uuid" NOT NULL,
    "user_id" "uuid" NOT NULL,
    "role" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "organization_members_role_check" CHECK (("role" = ANY (ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text", 'reviewer'::"text", 'viewer'::"text"])))
);


ALTER TABLE "public"."organization_members" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."organizations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" "text" NOT NULL,
    "slug" "text" NOT NULL,
    "created_by" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."organizations" OWNER TO "postgres";


COMMENT ON TABLE "public"."organizations" IS 'VRS tenant boundary.';



CREATE TABLE IF NOT EXISTS "public"."plan_catalog" (
    "plan_key" "text" NOT NULL,
    "name" "text" NOT NULL,
    "audience" "text" NOT NULL,
    "billing_status" "text" DEFAULT 'not_configured'::"text" NOT NULL,
    "currency" "text",
    "amount_minor" bigint,
    "limits" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "is_public" boolean DEFAULT false NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "plan_catalog_billing_status_check" CHECK (("billing_status" = ANY (ARRAY['not_configured'::"text", 'sandbox'::"text", 'live'::"text"])))
);


ALTER TABLE "public"."plan_catalog" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."production_adapter_status" WITH ("security_invoker"='true') AS
 SELECT "builder_key",
    "adapter_key",
    "configured",
    "target_type",
    "required_credentials",
    "can_deploy",
    "can_rollback",
    "can_health_check",
    "configuration",
    "updated_at",
        CASE
            WHEN "configured" THEN 'configured'::"text"
            ELSE 'unconfigured'::"text"
        END AS "status"
   FROM "private"."production_adapter_registry";


ALTER VIEW "public"."production_adapter_status" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."profiles" (
    "user_id" "uuid" NOT NULL,
    "display_name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."project_members" (
    "project_id" "uuid" NOT NULL,
    "user_id" "uuid" NOT NULL,
    "role" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "project_members_role_check" CHECK (("role" = ANY (ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text", 'reviewer'::"text", 'viewer'::"text"])))
);


ALTER TABLE "public"."project_members" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."projects" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "organization_id" "uuid" NOT NULL,
    "name" "text" NOT NULL,
    "slug" "text" NOT NULL,
    "description" "text",
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "created_by" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "projects_status_check" CHECK (("status" = ANY (ARRAY['draft'::"text", 'active'::"text", 'paused'::"text", 'archived'::"text"])))
);


ALTER TABLE "public"."projects" OWNER TO "postgres";


COMMENT ON TABLE "public"."projects" IS 'A SaaS/application build managed by VRS.';



CREATE TABLE IF NOT EXISTS "public"."reference_saas_templates" (
    "template_key" "text" NOT NULL,
    "name" "text" NOT NULL,
    "objective" "text" NOT NULL,
    "spec" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "recommended_slug" "text" NOT NULL,
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "reference_saas_templates_status_check" CHECK (("status" = ANY (ARRAY['active'::"text", 'deprecated'::"text"])))
);


ALTER TABLE "public"."reference_saas_templates" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."release_gates" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "factory_run_id" "uuid",
    "gate_key" "text" NOT NULL,
    "gate_type" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "score" numeric(5,2),
    "evidence" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "checked_at" timestamp with time zone,
    "checked_by" "uuid",
    CONSTRAINT "release_gates_gate_type_check" CHECK (("gate_type" = ANY (ARRAY['security'::"text", 'rls'::"text", 'auth'::"text", 'data_api'::"text", 'storage'::"text", 'rollback'::"text", 'qa'::"text", 'human_approval'::"text", 'production_lock'::"text", 'supply_chain'::"text"]))),
    CONSTRAINT "release_gates_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'pass'::"text", 'fail'::"text", 'blocked'::"text", 'waived'::"text"])))
);


ALTER TABLE "public"."release_gates" OWNER TO "postgres";


COMMENT ON TABLE "public"."release_gates" IS 'Evidence-backed release gates used by VRS certification.';



CREATE TABLE IF NOT EXISTS "public"."repair_recipe_registry" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "recipe_key" "text" NOT NULL,
    "failure_class" "text" NOT NULL,
    "signature_pattern" "text" NOT NULL,
    "builder_key" "text",
    "action_type" "text" NOT NULL,
    "action_spec" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "risk_level" "text" DEFAULT 'low'::"text" NOT NULL,
    "auto_apply" boolean DEFAULT false NOT NULL,
    "max_auto_attempts" integer DEFAULT 1 NOT NULL,
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "success_count" integer DEFAULT 0 NOT NULL,
    "failure_count" integer DEFAULT 0 NOT NULL,
    "confidence" numeric DEFAULT 0.50 NOT NULL,
    "last_verified_at" timestamp with time zone,
    CONSTRAINT "repair_recipe_registry_confidence_check" CHECK ((("confidence" >= (0)::numeric) AND ("confidence" <= (1)::numeric))),
    CONSTRAINT "repair_recipe_registry_max_auto_attempts_check" CHECK ((("max_auto_attempts" >= 0) AND ("max_auto_attempts" <= 5))),
    CONSTRAINT "repair_recipe_registry_risk_level_check" CHECK (("risk_level" = ANY (ARRAY['low'::"text", 'medium'::"text", 'high'::"text"]))),
    CONSTRAINT "repair_recipe_registry_status_check" CHECK (("status" = ANY (ARRAY['active'::"text", 'disabled'::"text", 'experimental'::"text"])))
);


ALTER TABLE "public"."repair_recipe_registry" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."spec_compilations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "app_spec_id" "uuid" NOT NULL,
    "compiler_version" "text" DEFAULT '1.0.0'::"text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "normalized_spec" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "validation_errors" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "module_plan" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "build_plan" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "created_by" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "builder_plan" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "capability_adapter_plan" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    CONSTRAINT "spec_compilations_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'valid'::"text", 'invalid'::"text", 'superseded'::"text"])))
);


ALTER TABLE "public"."spec_compilations" OWNER TO "postgres";


COMMENT ON TABLE "public"."spec_compilations" IS 'Deterministic normalization/validation output produced from an approved VRS App Spec.';



CREATE TABLE IF NOT EXISTS "public"."support_requests" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "customer_account_id" "uuid" NOT NULL,
    "opened_by" "uuid" NOT NULL,
    "severity" "text" DEFAULT 'normal'::"text" NOT NULL,
    "subject" "text" NOT NULL,
    "description" "text" NOT NULL,
    "status" "text" DEFAULT 'open'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "resolved_at" timestamp with time zone,
    CONSTRAINT "support_requests_description_check" CHECK ((("length"(TRIM(BOTH FROM "description")) >= 3) AND ("length"(TRIM(BOTH FROM "description")) <= 5000))),
    CONSTRAINT "support_requests_severity_check" CHECK (("severity" = ANY (ARRAY['low'::"text", 'normal'::"text", 'high'::"text", 'critical'::"text"]))),
    CONSTRAINT "support_requests_status_check" CHECK (("status" = ANY (ARRAY['open'::"text", 'acknowledged'::"text", 'resolved'::"text", 'closed'::"text"]))),
    CONSTRAINT "support_requests_subject_check" CHECK ((("length"(TRIM(BOTH FROM "subject")) >= 3) AND ("length"(TRIM(BOTH FROM "subject")) <= 200)))
);


ALTER TABLE "public"."support_requests" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."system_roles" (
    "user_id" "uuid" NOT NULL,
    "role" "text" NOT NULL,
    "claimed_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "system_roles_role_check" CHECK (("role" = ANY (ARRAY['founder'::"text", 'admin'::"text"])))
);


ALTER TABLE "public"."system_roles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."vl_cert_health" (
    "id" smallint NOT NULL,
    "status" "text" NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."vl_cert_health" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vl_factory_status" WITH ("security_invoker"='true') AS
 SELECT "r"."id" AS "factory_run_id",
    "r"."project_id",
    "r"."app_spec_id",
    "r"."workflow_id",
    "r"."input" AS "request_input",
    "s"."spec" AS "app_spec",
    COALESCE(("r"."plan" ->> 'builder_key'::"text"), ("r"."plan" ->> 'selected_builder'::"text"), ("r"."result" #>> '{runner,builder_key}'::"text"[])) AS "selected_builder",
    "r"."state" AS "factory_state",
    "r"."production_locked",
    "r"."target_environment",
    "r"."error_text" AS "factory_error",
    "j"."id" AS "runner_job_id",
    "j"."state" AS "runner_state",
    "j"."attempts" AS "runner_attempts",
    "j"."max_attempts" AS "runner_max_attempts",
    "j"."error_text" AS "runner_error",
    "fa"."id" AS "artifact_id",
    "fa"."name" AS "artifact_name",
    "fa"."sha256" AS "artifact_sha256",
    "fa"."storage_path" AS "artifact_location",
    "d"."id" AS "deployment_id",
    "d"."release_version",
    "d"."status" AS "deployment_status",
    "d"."certificate",
    "d"."approved_by",
    "d"."deployed_at",
    COALESCE(( SELECT "jsonb_object_agg"("g"."gate_key", "jsonb_build_object"('status', "g"."status", 'evidence', "g"."evidence", 'checked_at', "g"."checked_at")) AS "jsonb_object_agg"
           FROM "public"."release_gates" "g"
          WHERE ("g"."factory_run_id" = "r"."id")), '{}'::"jsonb") AS "release_gates",
    "a"."id" AS "approval_id",
    "a"."status" AS "approval_status",
    "a"."decided_by",
    "a"."decided_at",
    "p"."id" AS "promotion_job_id",
    "p"."state" AS "promotion_state",
    "p"."attempts" AS "promotion_attempts",
    "p"."max_attempts" AS "promotion_max_attempts",
    "p"."target_adapter",
    "p"."error_text" AS "promotion_error",
    "p"."result" AS "promotion_result",
    "ar"."configured" AS "adapter_configured",
    "ar"."target_type" AS "adapter_target_type",
    "ar"."can_rollback",
    "ar"."can_health_check",
    "r"."created_at" AS "factory_created_at",
    "r"."finished_at" AS "factory_finished_at",
    "j"."created_at" AS "runner_created_at",
    "j"."finished_at" AS "runner_finished_at",
    "fa"."created_at" AS "artifact_created_at",
    "d"."created_at" AS "deployment_created_at",
    "a"."requested_at" AS "approval_requested_at",
    "p"."created_at" AS "promotion_created_at",
    "p"."finished_at" AS "promotion_finished_at",
    COALESCE(( SELECT "jsonb_agg"("to_jsonb"("v".*) ORDER BY "v"."checked_at") AS "jsonb_agg"
           FROM "private"."production_deployment_verifications" "v"
          WHERE ("v"."deployment_id" = "d"."id")), '[]'::"jsonb") AS "health_verification",
    COALESCE(( SELECT "jsonb_agg"("to_jsonb"("rb".*) ORDER BY "rb"."requested_at" DESC) AS "jsonb_agg"
           FROM "private"."production_rollback_audits" "rb"
          WHERE ("rb"."deployment_id" = "d"."id")), '[]'::"jsonb") AS "rollback_history",
    COALESCE("p"."error_text", "j"."error_text", "r"."error_text") AS "current_error"
   FROM ((((((("public"."factory_runs" "r"
     LEFT JOIN "public"."app_specs" "s" ON (("s"."id" = "r"."app_spec_id")))
     LEFT JOIN "private"."runner_jobs" "j" ON (("j"."factory_run_id" = "r"."id")))
     LEFT JOIN LATERAL ( SELECT "x"."id",
            "x"."factory_run_id",
            "x"."project_id",
            "x"."artifact_type",
            "x"."name",
            "x"."storage_path",
            "x"."sha256",
            "x"."metadata",
            "x"."created_at"
           FROM "public"."factory_artifacts" "x"
          WHERE ("x"."factory_run_id" = "r"."id")
          ORDER BY "x"."created_at" DESC
         LIMIT 1) "fa" ON (true))
     LEFT JOIN "public"."deployments" "d" ON ((("d"."workflow_id" = "r"."workflow_id") AND ("d"."project_id" = "r"."project_id"))))
     LEFT JOIN "public"."approvals" "a" ON ((("a"."workflow_id" = "r"."workflow_id") AND ("a"."approval_type" = 'production_release'::"text"))))
     LEFT JOIN "private"."production_promotion_jobs" "p" ON (("p"."deployment_id" = "d"."id")))
     LEFT JOIN "private"."production_adapter_registry" "ar" ON (("ar"."builder_key" = COALESCE(("r"."plan" ->> 'builder_key'::"text"), ("r"."plan" ->> 'selected_builder'::"text"), ("r"."result" #>> '{runner,builder_key}'::"text"[])))));


ALTER VIEW "public"."vl_factory_status" OWNER TO "postgres";


COMMENT ON VIEW "public"."vl_factory_status" IS 'Authoritative service-role-only lifecycle status for the VL Command Centre.';



CREATE TABLE IF NOT EXISTS "public"."workflows" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "project_id" "uuid" NOT NULL,
    "app_spec_id" "uuid",
    "workflow_type" "text" NOT NULL,
    "state" "text" DEFAULT 'queued'::"text" NOT NULL,
    "input" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "output" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_by" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "started_at" timestamp with time zone,
    "finished_at" timestamp with time zone,
    CONSTRAINT "workflows_state_check" CHECK (("state" = ANY (ARRAY['queued'::"text", 'running'::"text", 'waiting_approval'::"text", 'succeeded'::"text", 'failed'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "public"."workflows" OWNER TO "postgres";


COMMENT ON TABLE "public"."workflows" IS 'Orchestrator workflow state.';



ALTER TABLE ONLY "private"."agent_capability_grants"
    ADD CONSTRAINT "agent_capability_grants_pkey" PRIMARY KEY ("grant_id");



ALTER TABLE ONLY "private"."agent_control_audit_events"
    ADD CONSTRAINT "agent_control_audit_events_action_id_event_seq_key" UNIQUE ("action_id", "event_seq");



ALTER TABLE ONLY "private"."agent_control_audit_events"
    ADD CONSTRAINT "agent_control_audit_events_event_digest_key" UNIQUE ("event_digest");



ALTER TABLE ONLY "private"."agent_control_audit_events"
    ADD CONSTRAINT "agent_control_audit_events_pkey" PRIMARY KEY ("event_id");



ALTER TABLE ONLY "private"."app_compiler_audit"
    ADD CONSTRAINT "app_compiler_audit_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."app_launch_audit"
    ADD CONSTRAINT "app_launch_audit_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."assisted_build_cost_policy"
    ADD CONSTRAINT "assisted_build_cost_policy_pkey" PRIMARY KEY ("complexity_class");



ALTER TABLE ONLY "private"."builder_certification_golden_profiles"
    ADD CONSTRAINT "builder_certification_golden_profiles_pkey" PRIMARY KEY ("builder_key");



ALTER TABLE ONLY "private"."builder_release_gate_profiles"
    ADD CONSTRAINT "builder_release_gate_profiles_pkey" PRIMARY KEY ("builder_key");



ALTER TABLE ONLY "private"."builder_route_decisions"
    ADD CONSTRAINT "builder_route_decisions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."capability_adapter_evidence"
    ADD CONSTRAINT "capability_adapter_evidence_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."capability_adapter_registry"
    ADD CONSTRAINT "capability_adapter_registry_pkey" PRIMARY KEY ("adapter_key");



ALTER TABLE ONLY "private"."capability_adapter_results"
    ADD CONSTRAINT "capability_adapter_results_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."factory_execution_events"
    ADD CONSTRAINT "factory_execution_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."internal_usage_audit"
    ADD CONSTRAINT "internal_usage_audit_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."internal_usage_ledger"
    ADD CONSTRAINT "internal_usage_ledger_factory_run_id_key" UNIQUE ("factory_run_id");



ALTER TABLE ONLY "private"."internal_usage_ledger"
    ADD CONSTRAINT "internal_usage_ledger_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."internal_usage_overrides"
    ADD CONSTRAINT "internal_usage_overrides_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."internal_usage_policy"
    ADD CONSTRAINT "internal_usage_policy_pkey" PRIMARY KEY ("singleton");



ALTER TABLE ONLY "private"."launch_readiness_checks"
    ADD CONSTRAINT "launch_readiness_checks_pkey" PRIMARY KEY ("check_key");



ALTER TABLE ONLY "private"."notification_events"
    ADD CONSTRAINT "notification_events_event_key_key" UNIQUE ("event_key");



ALTER TABLE ONLY "private"."notification_events"
    ADD CONSTRAINT "notification_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."notification_outbox"
    ADD CONSTRAINT "notification_outbox_idempotency_key_key" UNIQUE ("idempotency_key");



ALTER TABLE ONLY "private"."notification_outbox"
    ADD CONSTRAINT "notification_outbox_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."notification_outbox"
    ADD CONSTRAINT "notification_outbox_provider_message_id_key" UNIQUE ("provider_message_id");



ALTER TABLE ONLY "private"."notification_production_activations"
    ADD CONSTRAINT "notification_production_activations_adapter_key_key" UNIQUE ("adapter_key");



ALTER TABLE ONLY "private"."notification_production_activations"
    ADD CONSTRAINT "notification_production_activations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."notification_reconciliation_checks"
    ADD CONSTRAINT "notification_reconciliation_checks_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."operational_incidents"
    ADD CONSTRAINT "operational_incidents_incident_key_key" UNIQUE ("incident_key");



ALTER TABLE ONLY "private"."operational_incidents"
    ADD CONSTRAINT "operational_incidents_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."payment_fulfillment_events"
    ADD CONSTRAINT "payment_fulfillment_events_action_key_key" UNIQUE ("action_key");



ALTER TABLE ONLY "private"."payment_fulfillment_events"
    ADD CONSTRAINT "payment_fulfillment_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."payment_production_fulfillment_events"
    ADD CONSTRAINT "payment_production_fulfillment_events_action_key_key" UNIQUE ("action_key");



ALTER TABLE ONLY "private"."payment_production_fulfillment_events"
    ADD CONSTRAINT "payment_production_fulfillment_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."payment_production_orders"
    ADD CONSTRAINT "payment_production_orders_merchant_reference_key" UNIQUE ("merchant_reference");



ALTER TABLE ONLY "private"."payment_production_orders"
    ADD CONSTRAINT "payment_production_orders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."payment_production_orders"
    ADD CONSTRAINT "payment_production_orders_provider_bill_id_key" UNIQUE ("provider_bill_id");



ALTER TABLE ONLY "private"."payment_production_webhook_events"
    ADD CONSTRAINT "payment_production_webhook_events_event_key_key" UNIQUE ("event_key");



ALTER TABLE ONLY "private"."payment_production_webhook_events"
    ADD CONSTRAINT "payment_production_webhook_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."payment_reconciliation_checks"
    ADD CONSTRAINT "payment_reconciliation_checks_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."payment_sandbox_orders"
    ADD CONSTRAINT "payment_sandbox_orders_merchant_reference_key" UNIQUE ("merchant_reference");



ALTER TABLE ONLY "private"."payment_sandbox_orders"
    ADD CONSTRAINT "payment_sandbox_orders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."payment_sandbox_orders"
    ADD CONSTRAINT "payment_sandbox_orders_provider_bill_id_key" UNIQUE ("provider_bill_id");



ALTER TABLE ONLY "private"."payment_webhook_events"
    ADD CONSTRAINT "payment_webhook_events_event_key_key" UNIQUE ("event_key");



ALTER TABLE ONLY "private"."payment_webhook_events"
    ADD CONSTRAINT "payment_webhook_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."product_alignment_policy"
    ADD CONSTRAINT "product_alignment_policy_pkey" PRIMARY KEY ("policy_key");



ALTER TABLE ONLY "private"."production_adapter_registry"
    ADD CONSTRAINT "production_adapter_registry_pkey" PRIMARY KEY ("adapter_key");



ALTER TABLE ONLY "private"."production_deployment_verifications"
    ADD CONSTRAINT "production_deployment_verificati_promotion_job_id_check_key_key" UNIQUE ("promotion_job_id", "check_key");



ALTER TABLE ONLY "private"."production_deployment_verifications"
    ADD CONSTRAINT "production_deployment_verifications_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."production_promotion_jobs"
    ADD CONSTRAINT "production_promotion_jobs_deployment_id_key" UNIQUE ("deployment_id");



ALTER TABLE ONLY "private"."production_promotion_jobs"
    ADD CONSTRAINT "production_promotion_jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."production_rollback_audits"
    ADD CONSTRAINT "production_rollback_audits_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."release_validation_jobs"
    ADD CONSTRAINT "release_validation_jobs_deployment_id_key" UNIQUE ("deployment_id");



ALTER TABLE ONLY "private"."release_validation_jobs"
    ADD CONSTRAINT "release_validation_jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."runner_jobs"
    ADD CONSTRAINT "runner_jobs_factory_run_id_key" UNIQUE ("factory_run_id");



ALTER TABLE ONLY "private"."runner_jobs"
    ADD CONSTRAINT "runner_jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "private"."usage_counters"
    ADD CONSTRAINT "usage_counters_customer_account_id_metric_key_window_start__key" UNIQUE ("customer_account_id", "metric_key", "window_start", "window_end");



ALTER TABLE ONLY "private"."usage_counters"
    ADD CONSTRAINT "usage_counters_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."app_specs"
    ADD CONSTRAINT "app_specs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."app_specs"
    ADD CONSTRAINT "app_specs_project_id_version_key" UNIQUE ("project_id", "version");



ALTER TABLE ONLY "public"."approvals"
    ADD CONSTRAINT "approvals_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."audit_logs"
    ADD CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."build_failure_events"
    ADD CONSTRAINT "build_failure_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."build_steps"
    ADD CONSTRAINT "build_steps_factory_run_id_step_key_key" UNIQUE ("factory_run_id", "step_key");



ALTER TABLE ONLY "public"."build_steps"
    ADD CONSTRAINT "build_steps_factory_run_id_step_order_key" UNIQUE ("factory_run_id", "step_order");



ALTER TABLE ONLY "public"."build_steps"
    ADD CONSTRAINT "build_steps_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."builder_certification_evidence"
    ADD CONSTRAINT "builder_certification_evidence_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."builder_certification_policies"
    ADD CONSTRAINT "builder_certification_policies_builder_key_key" UNIQUE ("builder_key");



ALTER TABLE ONLY "public"."builder_certification_policies"
    ADD CONSTRAINT "builder_certification_policies_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."builder_certification_results"
    ADD CONSTRAINT "builder_certification_results_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."builder_registry"
    ADD CONSTRAINT "builder_registry_builder_key_key" UNIQUE ("builder_key");



ALTER TABLE ONLY "public"."builder_registry"
    ADD CONSTRAINT "builder_registry_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."ci_evidence_ingestions"
    ADD CONSTRAINT "ci_evidence_ingestions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."ci_evidence_ingestions"
    ADD CONSTRAINT "ci_evidence_ingestions_provider_repository_external_run_id__key" UNIQUE ("provider", "repository", "external_run_id", "builder_key");



ALTER TABLE ONLY "public"."ci_repair_actions"
    ADD CONSTRAINT "ci_repair_actions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."customer_accounts"
    ADD CONSTRAINT "customer_accounts_owner_user_id_key" UNIQUE ("owner_user_id");



ALTER TABLE ONLY "public"."customer_accounts"
    ADD CONSTRAINT "customer_accounts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."deployments"
    ADD CONSTRAINT "deployments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."environments"
    ADD CONSTRAINT "environments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."environments"
    ADD CONSTRAINT "environments_project_id_name_key" UNIQUE ("project_id", "name");



ALTER TABLE ONLY "public"."factory_artifacts"
    ADD CONSTRAINT "factory_artifacts_factory_run_id_name_key" UNIQUE ("factory_run_id", "name");



ALTER TABLE ONLY "public"."factory_artifacts"
    ADD CONSTRAINT "factory_artifacts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."factory_runs"
    ADD CONSTRAINT "factory_runs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."generated_artifacts"
    ADD CONSTRAINT "generated_artifacts_factory_run_id_path_key" UNIQUE ("factory_run_id", "path");



ALTER TABLE ONLY "public"."generated_artifacts"
    ADD CONSTRAINT "generated_artifacts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."jobs"
    ADD CONSTRAINT "jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."module_registry"
    ADD CONSTRAINT "module_registry_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."module_registry"
    ADD CONSTRAINT "module_registry_project_id_module_key_key" UNIQUE ("project_id", "module_key");



ALTER TABLE ONLY "public"."organization_members"
    ADD CONSTRAINT "organization_members_pkey" PRIMARY KEY ("organization_id", "user_id");



ALTER TABLE ONLY "public"."organizations"
    ADD CONSTRAINT "organizations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organizations"
    ADD CONSTRAINT "organizations_slug_key" UNIQUE ("slug");



ALTER TABLE ONLY "public"."plan_catalog"
    ADD CONSTRAINT "plan_catalog_pkey" PRIMARY KEY ("plan_key");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_pkey" PRIMARY KEY ("user_id");



ALTER TABLE ONLY "public"."project_members"
    ADD CONSTRAINT "project_members_pkey" PRIMARY KEY ("project_id", "user_id");



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_organization_id_slug_key" UNIQUE ("organization_id", "slug");



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."reference_saas_templates"
    ADD CONSTRAINT "reference_saas_templates_pkey" PRIMARY KEY ("template_key");



ALTER TABLE ONLY "public"."release_gates"
    ADD CONSTRAINT "release_gates_factory_run_id_gate_key_key" UNIQUE ("factory_run_id", "gate_key");



ALTER TABLE ONLY "public"."release_gates"
    ADD CONSTRAINT "release_gates_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."repair_recipe_registry"
    ADD CONSTRAINT "repair_recipe_registry_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."repair_recipe_registry"
    ADD CONSTRAINT "repair_recipe_registry_recipe_key_key" UNIQUE ("recipe_key");



ALTER TABLE ONLY "public"."spec_compilations"
    ADD CONSTRAINT "spec_compilations_app_spec_id_compiler_version_key" UNIQUE ("app_spec_id", "compiler_version");



ALTER TABLE ONLY "public"."spec_compilations"
    ADD CONSTRAINT "spec_compilations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."support_requests"
    ADD CONSTRAINT "support_requests_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."system_roles"
    ADD CONSTRAINT "system_roles_pkey" PRIMARY KEY ("user_id");



ALTER TABLE ONLY "public"."vl_cert_health"
    ADD CONSTRAINT "vl_cert_health_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."workflows"
    ADD CONSTRAINT "workflows_pkey" PRIMARY KEY ("id");



CREATE INDEX "agent_capability_grants_agent_idx" ON "private"."agent_capability_grants" USING "btree" ("agent_id", "valid_from" DESC);



CREATE INDEX "agent_capability_grants_parent_idx" ON "private"."agent_capability_grants" USING "btree" ("delegated_from_grant_id") WHERE ("delegated_from_grant_id" IS NOT NULL);



CREATE INDEX "agent_control_audit_action_idx" ON "private"."agent_control_audit_events" USING "btree" ("action_id", "event_seq");



CREATE INDEX "capability_adapter_evidence_adapter_key_idx" ON "private"."capability_adapter_evidence" USING "btree" ("adapter_key");



CREATE INDEX "capability_adapter_evidence_source_factory_run_id_idx" ON "private"."capability_adapter_evidence" USING "btree" ("source_factory_run_id");



CREATE INDEX "capability_adapter_evidence_source_project_id_idx" ON "private"."capability_adapter_evidence" USING "btree" ("source_project_id");



CREATE INDEX "capability_adapter_results_adapter_key_idx" ON "private"."capability_adapter_results" USING "btree" ("adapter_key");



CREATE INDEX "factory_execution_events_project_id_idx" ON "private"."factory_execution_events" USING "btree" ("project_id");



CREATE INDEX "factory_execution_events_run_idx" ON "private"."factory_execution_events" USING "btree" ("factory_run_id", "created_at");



CREATE INDEX "internal_usage_ledger_actor_day_idx" ON "private"."internal_usage_ledger" USING "btree" ("requested_by", "recorded_at");



CREATE INDEX "internal_usage_overrides_active_idx" ON "private"."internal_usage_overrides" USING "btree" ("project_id", "requested_by", "expires_at") WHERE ("revoked_at" IS NULL);



CREATE INDEX "notification_events_adapter_key_idx" ON "private"."notification_events" USING "btree" ("adapter_key");



CREATE INDEX "notification_outbox_adapter_key_idx" ON "private"."notification_outbox" USING "btree" ("adapter_key");



CREATE UNIQUE INDEX "notification_outbox_sandbox_idem_uidx" ON "private"."notification_outbox" USING "btree" ("adapter_key", "environment", "idempotency_key");



CREATE INDEX "notification_reconciliation_checks_adapter_key_idx" ON "private"."notification_reconciliation_checks" USING "btree" ("adapter_key");



CREATE INDEX "notification_reconciliation_checks_outbox_id_idx" ON "private"."notification_reconciliation_checks" USING "btree" ("outbox_id");



CREATE INDEX "operational_incidents_alert_queue_idx" ON "private"."operational_incidents" USING "btree" ("alert_state", "severity", "started_at") WHERE ("status" <> 'resolved'::"text");



CREATE INDEX "payment_fulfillment_events_order_id_idx" ON "private"."payment_fulfillment_events" USING "btree" ("order_id");



CREATE INDEX "payment_production_fulfillment_events_order_id_idx" ON "private"."payment_production_fulfillment_events" USING "btree" ("order_id");



CREATE INDEX "payment_reconciliation_checks_adapter_key_idx" ON "private"."payment_reconciliation_checks" USING "btree" ("adapter_key");



CREATE INDEX "payment_reconciliation_checks_order_id_idx" ON "private"."payment_reconciliation_checks" USING "btree" ("order_id");



CREATE INDEX "payment_sandbox_orders_adapter_key_idx" ON "private"."payment_sandbox_orders" USING "btree" ("adapter_key");



CREATE INDEX "payment_webhook_events_adapter_key_idx" ON "private"."payment_webhook_events" USING "btree" ("adapter_key");



CREATE UNIQUE INDEX "production_adapter_registry_builder_key_uidx" ON "private"."production_adapter_registry" USING "btree" ("builder_key");



CREATE INDEX "production_deployment_verifications_deployment_id_idx" ON "private"."production_deployment_verifications" USING "btree" ("deployment_id");



CREATE INDEX "production_promotion_jobs_builder_key_idx" ON "private"."production_promotion_jobs" USING "btree" ("builder_key");



CREATE INDEX "production_promotion_jobs_factory_run_id_idx" ON "private"."production_promotion_jobs" USING "btree" ("factory_run_id");



CREATE INDEX "production_promotion_jobs_project_id_idx" ON "private"."production_promotion_jobs" USING "btree" ("project_id");



CREATE INDEX "production_rollback_audits_deployment_id_idx" ON "private"."production_rollback_audits" USING "btree" ("deployment_id");



CREATE INDEX "production_rollback_audits_previous_deployment_id_idx" ON "private"."production_rollback_audits" USING "btree" ("previous_deployment_id");



CREATE INDEX "production_rollback_audits_requested_by_idx" ON "private"."production_rollback_audits" USING "btree" ("requested_by");



CREATE INDEX "release_validation_jobs_builder_key_idx" ON "private"."release_validation_jobs" USING "btree" ("builder_key");



CREATE INDEX "release_validation_jobs_factory_run_id_idx" ON "private"."release_validation_jobs" USING "btree" ("factory_run_id");



CREATE INDEX "release_validation_jobs_project_id_idx" ON "private"."release_validation_jobs" USING "btree" ("project_id");



CREATE INDEX "runner_jobs_project_id_idx" ON "private"."runner_jobs" USING "btree" ("project_id");



CREATE INDEX "usage_counters_customer_metric_idx" ON "private"."usage_counters" USING "btree" ("customer_account_id", "metric_key", "window_end");



CREATE INDEX "app_specs_approved_by_idx" ON "public"."app_specs" USING "btree" ("approved_by") WHERE ("approved_by" IS NOT NULL);



CREATE INDEX "app_specs_created_by_idx" ON "public"."app_specs" USING "btree" ("created_by");



CREATE INDEX "app_specs_project_idx" ON "public"."app_specs" USING "btree" ("project_id", "version" DESC);



CREATE INDEX "approvals_decided_by_idx" ON "public"."approvals" USING "btree" ("decided_by") WHERE ("decided_by" IS NOT NULL);



CREATE INDEX "approvals_factory_run_id_idx" ON "public"."approvals" USING "btree" ("factory_run_id");



CREATE UNIQUE INDEX "approvals_factory_run_type_uidx" ON "public"."approvals" USING "btree" ("factory_run_id", "approval_type");



CREATE INDEX "approvals_project_status_idx" ON "public"."approvals" USING "btree" ("project_id", "status", "requested_at" DESC);



CREATE INDEX "approvals_requested_by_idx" ON "public"."approvals" USING "btree" ("requested_by");



CREATE INDEX "approvals_workflow_idx" ON "public"."approvals" USING "btree" ("workflow_id") WHERE ("workflow_id" IS NOT NULL);



CREATE INDEX "audit_logs_actor_idx" ON "public"."audit_logs" USING "btree" ("actor_user_id", "created_at" DESC);



CREATE INDEX "audit_logs_org_idx" ON "public"."audit_logs" USING "btree" ("organization_id", "created_at" DESC);



CREATE INDEX "audit_logs_project_idx" ON "public"."audit_logs" USING "btree" ("project_id", "created_at" DESC);



CREATE INDEX "build_failure_events_build_step_id_idx" ON "public"."build_failure_events" USING "btree" ("build_step_id");



CREATE INDEX "build_failure_events_project_id_idx" ON "public"."build_failure_events" USING "btree" ("project_id");



CREATE INDEX "build_failure_events_run_idx" ON "public"."build_failure_events" USING "btree" ("factory_run_id", "created_at" DESC);



CREATE INDEX "build_failure_events_signature_idx" ON "public"."build_failure_events" USING "btree" ("signature", "created_at" DESC);



CREATE INDEX "build_steps_project_idx" ON "public"."build_steps" USING "btree" ("project_id");



CREATE INDEX "build_steps_run_state_idx" ON "public"."build_steps" USING "btree" ("factory_run_id", "state", "step_order");



CREATE INDEX "builder_cert_evidence_idx" ON "public"."builder_certification_evidence" USING "btree" ("builder_key", "created_at" DESC);



CREATE INDEX "builder_certification_evidence_factory_run_id_idx" ON "public"."builder_certification_evidence" USING "btree" ("factory_run_id");



CREATE INDEX "builder_certification_evidence_project_id_idx" ON "public"."builder_certification_evidence" USING "btree" ("project_id");



CREATE INDEX "builder_certification_results_builder_time_idx" ON "public"."builder_certification_results" USING "btree" ("builder_key", "evaluated_at" DESC);



CREATE INDEX "ci_evidence_ingestions_builder_key_idx" ON "public"."ci_evidence_ingestions" USING "btree" ("builder_key");



CREATE INDEX "ci_evidence_ingestions_factory_run_id_idx" ON "public"."ci_evidence_ingestions" USING "btree" ("factory_run_id");



CREATE INDEX "ci_evidence_ingestions_project_id_idx" ON "public"."ci_evidence_ingestions" USING "btree" ("project_id");



CREATE INDEX "ci_repair_actions_builder_key_idx" ON "public"."ci_repair_actions" USING "btree" ("builder_key");



CREATE INDEX "ci_repair_actions_factory_run_idx" ON "public"."ci_repair_actions" USING "btree" ("factory_run_id", "created_at" DESC);



CREATE INDEX "ci_repair_actions_failure_event_id_idx" ON "public"."ci_repair_actions" USING "btree" ("failure_event_id");



CREATE INDEX "ci_repair_actions_project_id_idx" ON "public"."ci_repair_actions" USING "btree" ("project_id");



CREATE INDEX "ci_repair_actions_recipe_key_idx" ON "public"."ci_repair_actions" USING "btree" ("recipe_key");



CREATE INDEX "ci_repair_actions_state_idx" ON "public"."ci_repair_actions" USING "btree" ("state", "created_at" DESC);



CREATE INDEX "customer_accounts_plan_key_idx" ON "public"."customer_accounts" USING "btree" ("plan_key");



CREATE INDEX "customer_accounts_status_idx" ON "public"."customer_accounts" USING "btree" ("status");



CREATE INDEX "deployments_approved_by_idx" ON "public"."deployments" USING "btree" ("approved_by") WHERE ("approved_by" IS NOT NULL);



CREATE INDEX "deployments_created_by_idx" ON "public"."deployments" USING "btree" ("created_by");



CREATE INDEX "deployments_environment_idx" ON "public"."deployments" USING "btree" ("environment_id");



CREATE UNIQUE INDEX "deployments_factory_run_environment_uidx" ON "public"."deployments" USING "btree" ("factory_run_id", "environment_id");



CREATE INDEX "deployments_factory_run_id_idx" ON "public"."deployments" USING "btree" ("factory_run_id");



CREATE INDEX "deployments_project_idx" ON "public"."deployments" USING "btree" ("project_id", "created_at" DESC);



CREATE INDEX "deployments_workflow_idx" ON "public"."deployments" USING "btree" ("workflow_id") WHERE ("workflow_id" IS NOT NULL);



CREATE INDEX "environments_project_idx" ON "public"."environments" USING "btree" ("project_id", "kind");



CREATE INDEX "factory_artifacts_project_idx" ON "public"."factory_artifacts" USING "btree" ("project_id");



CREATE INDEX "factory_artifacts_run_idx" ON "public"."factory_artifacts" USING "btree" ("factory_run_id");



CREATE INDEX "factory_runs_app_spec_idx" ON "public"."factory_runs" USING "btree" ("app_spec_id");



CREATE INDEX "factory_runs_project_state_idx" ON "public"."factory_runs" USING "btree" ("project_id", "state");



CREATE INDEX "factory_runs_requested_by_idx" ON "public"."factory_runs" USING "btree" ("requested_by");



CREATE INDEX "factory_runs_workflow_idx" ON "public"."factory_runs" USING "btree" ("workflow_id");



CREATE INDEX "generated_artifacts_project_idx" ON "public"."generated_artifacts" USING "btree" ("project_id");



CREATE INDEX "generated_artifacts_step_idx" ON "public"."generated_artifacts" USING "btree" ("build_step_id");



CREATE INDEX "idx_app_specs_parent_app_spec_id" ON "public"."app_specs" USING "btree" ("parent_app_spec_id");



CREATE INDEX "idx_factory_runs_base_factory_run_id" ON "public"."factory_runs" USING "btree" ("base_factory_run_id");



CREATE INDEX "jobs_workflow_state_idx" ON "public"."jobs" USING "btree" ("workflow_id", "state");



CREATE INDEX "module_registry_created_by_idx" ON "public"."module_registry" USING "btree" ("created_by");



CREATE INDEX "module_registry_project_status_idx" ON "public"."module_registry" USING "btree" ("project_id", "status");



CREATE INDEX "organization_members_user_idx" ON "public"."organization_members" USING "btree" ("user_id", "organization_id");



CREATE INDEX "organizations_created_by_idx" ON "public"."organizations" USING "btree" ("created_by");



CREATE INDEX "project_members_user_idx" ON "public"."project_members" USING "btree" ("user_id", "project_id");



CREATE INDEX "projects_created_by_idx" ON "public"."projects" USING "btree" ("created_by");



CREATE INDEX "projects_org_idx" ON "public"."projects" USING "btree" ("organization_id", "status");



CREATE INDEX "release_gates_checked_by_idx" ON "public"."release_gates" USING "btree" ("checked_by");



CREATE INDEX "release_gates_project_status_idx" ON "public"."release_gates" USING "btree" ("project_id", "status");



CREATE INDEX "release_gates_run_idx" ON "public"."release_gates" USING "btree" ("factory_run_id");



CREATE INDEX "repair_recipe_registry_match_idx" ON "public"."repair_recipe_registry" USING "btree" ("failure_class", "builder_key", "status");



CREATE INDEX "spec_compilations_app_spec_idx" ON "public"."spec_compilations" USING "btree" ("app_spec_id");



CREATE INDEX "spec_compilations_created_by_idx" ON "public"."spec_compilations" USING "btree" ("created_by");



CREATE INDEX "spec_compilations_project_idx" ON "public"."spec_compilations" USING "btree" ("project_id");



CREATE INDEX "support_requests_customer_account_id_idx" ON "public"."support_requests" USING "btree" ("customer_account_id");



CREATE INDEX "support_requests_opened_by_idx" ON "public"."support_requests" USING "btree" ("opened_by");



CREATE INDEX "support_requests_status_created_idx" ON "public"."support_requests" USING "btree" ("status", "created_at" DESC);



CREATE INDEX "workflows_app_spec_idx" ON "public"."workflows" USING "btree" ("app_spec_id") WHERE ("app_spec_id" IS NOT NULL);



CREATE INDEX "workflows_created_by_idx" ON "public"."workflows" USING "btree" ("created_by");



CREATE INDEX "workflows_project_state_idx" ON "public"."workflows" USING "btree" ("project_id", "state", "created_at" DESC);



CREATE OR REPLACE TRIGGER "trg_agent_capability_grant_validate" BEFORE INSERT OR UPDATE ON "private"."agent_capability_grants" FOR EACH ROW EXECUTE FUNCTION "private"."validate_agent_capability_grant"();



CREATE OR REPLACE TRIGGER "trg_agent_control_audit_chain" BEFORE INSERT ON "private"."agent_control_audit_events" FOR EACH ROW EXECUTE FUNCTION "private"."validate_agent_audit_chain"();



CREATE OR REPLACE TRIGGER "trg_agent_control_audit_no_delete" BEFORE DELETE ON "private"."agent_control_audit_events" FOR EACH ROW EXECUTE FUNCTION "private"."block_agent_audit_mutation"();



CREATE OR REPLACE TRIGGER "trg_agent_control_audit_no_truncate" BEFORE TRUNCATE ON "private"."agent_control_audit_events" FOR EACH STATEMENT EXECUTE FUNCTION "private"."block_agent_audit_mutation"();



CREATE OR REPLACE TRIGGER "trg_agent_control_audit_no_update" BEFORE UPDATE ON "private"."agent_control_audit_events" FOR EACH ROW EXECUTE FUNCTION "private"."block_agent_audit_mutation"();



CREATE OR REPLACE TRIGGER "trg_internal_usage_override_request" INSTEAD OF INSERT ON "private"."internal_usage_override_request" FOR EACH ROW EXECUTE FUNCTION "private"."request_vrs_internal_usage_override_impl"();



CREATE OR REPLACE TRIGGER "trg_refresh_builder_gate_profile_version" BEFORE INSERT OR UPDATE ON "private"."builder_release_gate_profiles" FOR EACH ROW EXECUTE FUNCTION "private"."refresh_builder_gate_profile_version"();



CREATE OR REPLACE TRIGGER "trg_sync_successful_rollback_rehearsal_gate" AFTER UPDATE OF "state", "result", "finished_at" ON "private"."production_rollback_audits" FOR EACH ROW WHEN (("new"."state" = 'succeeded'::"text")) EXECUTE FUNCTION "private"."sync_successful_rollback_rehearsal_gate"();



CREATE OR REPLACE TRIGGER "generated_artifacts_secret_guard" BEFORE INSERT OR UPDATE OF "content" ON "public"."generated_artifacts" FOR EACH ROW EXECUTE FUNCTION "private"."reject_generated_artifact_secrets"();



CREATE OR REPLACE TRIGGER "organizations_touch_updated_at" BEFORE UPDATE ON "public"."organizations" FOR EACH ROW EXECUTE FUNCTION "public"."touch_updated_at"();



CREATE OR REPLACE TRIGGER "profiles_touch_updated_at" BEFORE UPDATE ON "public"."profiles" FOR EACH ROW EXECUTE FUNCTION "public"."touch_updated_at"();



CREATE OR REPLACE TRIGGER "projects_touch_updated_at" BEFORE UPDATE ON "public"."projects" FOR EACH ROW EXECUTE FUNCTION "public"."touch_updated_at"();



CREATE OR REPLACE TRIGGER "trg_assisted_build_execution_gate" BEFORE INSERT ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_assisted_build_execution_gate"();



CREATE OR REPLACE TRIGGER "trg_auto_prepare_release_candidate" AFTER UPDATE OF "state", "result" ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."auto_prepare_release_candidate"();



CREATE OR REPLACE TRIGGER "trg_builder_activation_guard" BEFORE UPDATE OF "status" ON "public"."builder_registry" FOR EACH ROW EXECUTE FUNCTION "public"."guard_builder_activation"();



CREATE OR REPLACE TRIGGER "trg_enforce_approval_identity_binding" BEFORE UPDATE ON "public"."approvals" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_release_identity_binding"();



CREATE OR REPLACE TRIGGER "trg_enforce_deployment_identity_binding" BEFORE UPDATE ON "public"."deployments" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_release_identity_binding"();



CREATE OR REPLACE TRIGGER "trg_enforce_deployment_snapshot_immutability" BEFORE INSERT OR UPDATE ON "public"."deployments" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_deployment_snapshot_immutability"();



CREATE OR REPLACE TRIGGER "trg_enforce_factory_artifact_immutability" BEFORE INSERT OR DELETE OR UPDATE ON "public"."factory_artifacts" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_factory_artifact_immutability"();



CREATE OR REPLACE TRIGGER "trg_enforce_production_deployment_guard" BEFORE INSERT OR UPDATE ON "public"."deployments" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_production_deployment_guard"();



CREATE OR REPLACE TRIGGER "trg_enforce_public_factory_quota" BEFORE INSERT ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_public_factory_quota"();



CREATE OR REPLACE TRIGGER "trg_enqueue_factory_runner_job" AFTER INSERT OR UPDATE OF "state", "input", "plan" ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."enqueue_factory_runner_job"();



CREATE OR REPLACE TRIGGER "trg_enqueue_production_promotion_job" AFTER INSERT OR UPDATE OF "status" ON "public"."deployments" FOR EACH ROW EXECUTE FUNCTION "private"."enqueue_production_promotion_job"();



CREATE OR REPLACE TRIGGER "trg_enqueue_release_validation_job" AFTER INSERT OR UPDATE OF "status" ON "public"."deployments" FOR EACH ROW EXECUTE FUNCTION "private"."enqueue_release_validation_job"();



CREATE OR REPLACE TRIGGER "trg_ensure_default_project_environments" AFTER INSERT ON "public"."projects" FOR EACH ROW EXECUTE FUNCTION "private"."ensure_default_project_environments"();



CREATE OR REPLACE TRIGGER "trg_factory_run_capability_plan" BEFORE INSERT OR UPDATE OF "input", "plan" ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."enrich_factory_run_capability_plan"();



CREATE OR REPLACE TRIGGER "trg_factory_runs_product_alignment" BEFORE INSERT ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_product_alignment_on_factory_run"();



CREATE OR REPLACE TRIGGER "trg_factory_runs_require_approved_spec" BEFORE INSERT OR UPDATE OF "app_spec_id", "run_type" ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."enforce_approved_app_spec_for_factory_run"();



CREATE OR REPLACE TRIGGER "trg_guard_customer_account_mutation" BEFORE INSERT OR UPDATE ON "public"."customer_accounts" FOR EACH ROW EXECUTE FUNCTION "private"."guard_customer_account_mutation"();



CREATE OR REPLACE TRIGGER "trg_guard_factory_awaiting_approval" BEFORE UPDATE OF "state" ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."guard_factory_awaiting_approval_requires_certified_deployment"();



CREATE OR REPLACE TRIGGER "trg_guard_supply_chain_attestation_gate" BEFORE UPDATE ON "public"."release_gates" FOR EACH ROW EXECUTE FUNCTION "private"."guard_supply_chain_attestation_gate"();



CREATE OR REPLACE TRIGGER "trg_normalize_generated_mobile_source" BEFORE INSERT OR UPDATE OF "content" ON "public"."generated_artifacts" FOR EACH ROW EXECUTE FUNCTION "private"."normalize_generated_mobile_source"();



CREATE OR REPLACE TRIGGER "trg_seed_factory_additional_sources" AFTER INSERT ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."seed_factory_additional_sources"();



CREATE OR REPLACE TRIGGER "trg_seed_factory_sources" AFTER INSERT ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."seed_factory_sources"();



CREATE OR REPLACE TRIGGER "trg_seed_gis_kml_export_source" AFTER INSERT ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."seed_gis_kml_export_source"();



CREATE OR REPLACE TRIGGER "trg_seed_mobile_android_manifest" AFTER INSERT ON "public"."factory_runs" FOR EACH ROW EXECUTE FUNCTION "private"."seed_mobile_android_manifest"();



CREATE OR REPLACE TRIGGER "trg_spec_compilation_capability_plan" BEFORE INSERT OR UPDATE OF "normalized_spec", "module_plan" ON "public"."spec_compilations" FOR EACH ROW EXECUTE FUNCTION "private"."set_spec_compilation_capability_plan"();



ALTER TABLE ONLY "private"."agent_capability_grants"
    ADD CONSTRAINT "agent_capability_grants_delegated_from_grant_id_fkey" FOREIGN KEY ("delegated_from_grant_id") REFERENCES "private"."agent_capability_grants"("grant_id");



ALTER TABLE ONLY "private"."builder_certification_golden_profiles"
    ADD CONSTRAINT "builder_certification_golden_profiles_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key");



ALTER TABLE ONLY "private"."builder_release_gate_profiles"
    ADD CONSTRAINT "builder_release_gate_profiles_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."capability_adapter_evidence"
    ADD CONSTRAINT "capability_adapter_evidence_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."capability_adapter_evidence"
    ADD CONSTRAINT "capability_adapter_evidence_source_factory_run_id_fkey" FOREIGN KEY ("source_factory_run_id") REFERENCES "public"."factory_runs"("id");



ALTER TABLE ONLY "private"."capability_adapter_evidence"
    ADD CONSTRAINT "capability_adapter_evidence_source_project_id_fkey" FOREIGN KEY ("source_project_id") REFERENCES "public"."projects"("id");



ALTER TABLE ONLY "private"."capability_adapter_results"
    ADD CONSTRAINT "capability_adapter_results_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."factory_execution_events"
    ADD CONSTRAINT "factory_execution_events_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."factory_execution_events"
    ADD CONSTRAINT "factory_execution_events_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."internal_usage_ledger"
    ADD CONSTRAINT "internal_usage_ledger_override_id_fkey" FOREIGN KEY ("override_id") REFERENCES "private"."internal_usage_overrides"("id");



ALTER TABLE ONLY "private"."internal_usage_ledger"
    ADD CONSTRAINT "internal_usage_ledger_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."internal_usage_overrides"
    ADD CONSTRAINT "internal_usage_overrides_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."notification_events"
    ADD CONSTRAINT "notification_events_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key");



ALTER TABLE ONLY "private"."notification_outbox"
    ADD CONSTRAINT "notification_outbox_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key");



ALTER TABLE ONLY "private"."notification_reconciliation_checks"
    ADD CONSTRAINT "notification_reconciliation_checks_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key");



ALTER TABLE ONLY "private"."notification_reconciliation_checks"
    ADD CONSTRAINT "notification_reconciliation_checks_outbox_id_fkey" FOREIGN KEY ("outbox_id") REFERENCES "private"."notification_outbox"("id");



ALTER TABLE ONLY "private"."payment_fulfillment_events"
    ADD CONSTRAINT "payment_fulfillment_events_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "private"."payment_sandbox_orders"("id");



ALTER TABLE ONLY "private"."payment_production_fulfillment_events"
    ADD CONSTRAINT "payment_production_fulfillment_events_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "private"."payment_production_orders"("id");



ALTER TABLE ONLY "private"."payment_reconciliation_checks"
    ADD CONSTRAINT "payment_reconciliation_checks_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key");



ALTER TABLE ONLY "private"."payment_reconciliation_checks"
    ADD CONSTRAINT "payment_reconciliation_checks_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "private"."payment_sandbox_orders"("id");



ALTER TABLE ONLY "private"."payment_sandbox_orders"
    ADD CONSTRAINT "payment_sandbox_orders_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key");



ALTER TABLE ONLY "private"."payment_webhook_events"
    ADD CONSTRAINT "payment_webhook_events_adapter_key_fkey" FOREIGN KEY ("adapter_key") REFERENCES "private"."capability_adapter_registry"("adapter_key");



ALTER TABLE ONLY "private"."production_deployment_verifications"
    ADD CONSTRAINT "production_deployment_verifications_deployment_id_fkey" FOREIGN KEY ("deployment_id") REFERENCES "public"."deployments"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."production_deployment_verifications"
    ADD CONSTRAINT "production_deployment_verifications_promotion_job_id_fkey" FOREIGN KEY ("promotion_job_id") REFERENCES "private"."production_promotion_jobs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."production_promotion_jobs"
    ADD CONSTRAINT "production_promotion_jobs_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key");



ALTER TABLE ONLY "private"."production_promotion_jobs"
    ADD CONSTRAINT "production_promotion_jobs_deployment_id_fkey" FOREIGN KEY ("deployment_id") REFERENCES "public"."deployments"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."production_promotion_jobs"
    ADD CONSTRAINT "production_promotion_jobs_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."production_promotion_jobs"
    ADD CONSTRAINT "production_promotion_jobs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."production_rollback_audits"
    ADD CONSTRAINT "production_rollback_audits_deployment_id_fkey" FOREIGN KEY ("deployment_id") REFERENCES "public"."deployments"("id");



ALTER TABLE ONLY "private"."production_rollback_audits"
    ADD CONSTRAINT "production_rollback_audits_previous_deployment_id_fkey" FOREIGN KEY ("previous_deployment_id") REFERENCES "public"."deployments"("id");



ALTER TABLE ONLY "private"."production_rollback_audits"
    ADD CONSTRAINT "production_rollback_audits_requested_by_fkey" FOREIGN KEY ("requested_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "private"."release_validation_jobs"
    ADD CONSTRAINT "release_validation_jobs_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key");



ALTER TABLE ONLY "private"."release_validation_jobs"
    ADD CONSTRAINT "release_validation_jobs_deployment_id_fkey" FOREIGN KEY ("deployment_id") REFERENCES "public"."deployments"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."release_validation_jobs"
    ADD CONSTRAINT "release_validation_jobs_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."release_validation_jobs"
    ADD CONSTRAINT "release_validation_jobs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."runner_jobs"
    ADD CONSTRAINT "runner_jobs_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."runner_jobs"
    ADD CONSTRAINT "runner_jobs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "private"."usage_counters"
    ADD CONSTRAINT "usage_counters_customer_account_id_fkey" FOREIGN KEY ("customer_account_id") REFERENCES "public"."customer_accounts"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."app_specs"
    ADD CONSTRAINT "app_specs_approved_by_fkey" FOREIGN KEY ("approved_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."app_specs"
    ADD CONSTRAINT "app_specs_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."app_specs"
    ADD CONSTRAINT "app_specs_parent_app_spec_id_fkey" FOREIGN KEY ("parent_app_spec_id") REFERENCES "public"."app_specs"("id");



ALTER TABLE ONLY "public"."app_specs"
    ADD CONSTRAINT "app_specs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."approvals"
    ADD CONSTRAINT "approvals_decided_by_fkey" FOREIGN KEY ("decided_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."approvals"
    ADD CONSTRAINT "approvals_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id");



ALTER TABLE ONLY "public"."approvals"
    ADD CONSTRAINT "approvals_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."approvals"
    ADD CONSTRAINT "approvals_requested_by_fkey" FOREIGN KEY ("requested_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."approvals"
    ADD CONSTRAINT "approvals_workflow_id_fkey" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."audit_logs"
    ADD CONSTRAINT "audit_logs_actor_user_id_fkey" FOREIGN KEY ("actor_user_id") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."audit_logs"
    ADD CONSTRAINT "audit_logs_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."audit_logs"
    ADD CONSTRAINT "audit_logs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."build_failure_events"
    ADD CONSTRAINT "build_failure_events_build_step_id_fkey" FOREIGN KEY ("build_step_id") REFERENCES "public"."build_steps"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."build_failure_events"
    ADD CONSTRAINT "build_failure_events_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."build_failure_events"
    ADD CONSTRAINT "build_failure_events_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."build_steps"
    ADD CONSTRAINT "build_steps_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."build_steps"
    ADD CONSTRAINT "build_steps_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."builder_certification_evidence"
    ADD CONSTRAINT "builder_certification_evidence_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."builder_certification_evidence"
    ADD CONSTRAINT "builder_certification_evidence_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."builder_certification_evidence"
    ADD CONSTRAINT "builder_certification_evidence_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."builder_certification_policies"
    ADD CONSTRAINT "builder_certification_policies_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."builder_certification_results"
    ADD CONSTRAINT "builder_certification_results_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."ci_evidence_ingestions"
    ADD CONSTRAINT "ci_evidence_ingestions_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key");



ALTER TABLE ONLY "public"."ci_evidence_ingestions"
    ADD CONSTRAINT "ci_evidence_ingestions_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."ci_evidence_ingestions"
    ADD CONSTRAINT "ci_evidence_ingestions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."ci_repair_actions"
    ADD CONSTRAINT "ci_repair_actions_builder_key_fkey" FOREIGN KEY ("builder_key") REFERENCES "public"."builder_registry"("builder_key");



ALTER TABLE ONLY "public"."ci_repair_actions"
    ADD CONSTRAINT "ci_repair_actions_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."ci_repair_actions"
    ADD CONSTRAINT "ci_repair_actions_failure_event_id_fkey" FOREIGN KEY ("failure_event_id") REFERENCES "public"."build_failure_events"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."ci_repair_actions"
    ADD CONSTRAINT "ci_repair_actions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."ci_repair_actions"
    ADD CONSTRAINT "ci_repair_actions_recipe_key_fkey" FOREIGN KEY ("recipe_key") REFERENCES "public"."repair_recipe_registry"("recipe_key");



ALTER TABLE ONLY "public"."customer_accounts"
    ADD CONSTRAINT "customer_accounts_owner_user_id_fkey" FOREIGN KEY ("owner_user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."customer_accounts"
    ADD CONSTRAINT "customer_accounts_plan_key_fkey" FOREIGN KEY ("plan_key") REFERENCES "public"."plan_catalog"("plan_key");



ALTER TABLE ONLY "public"."deployments"
    ADD CONSTRAINT "deployments_approved_by_fkey" FOREIGN KEY ("approved_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."deployments"
    ADD CONSTRAINT "deployments_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."deployments"
    ADD CONSTRAINT "deployments_environment_id_fkey" FOREIGN KEY ("environment_id") REFERENCES "public"."environments"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."deployments"
    ADD CONSTRAINT "deployments_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id");



ALTER TABLE ONLY "public"."deployments"
    ADD CONSTRAINT "deployments_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."deployments"
    ADD CONSTRAINT "deployments_workflow_id_fkey" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."environments"
    ADD CONSTRAINT "environments_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."factory_artifacts"
    ADD CONSTRAINT "factory_artifacts_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."factory_artifacts"
    ADD CONSTRAINT "factory_artifacts_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."factory_runs"
    ADD CONSTRAINT "factory_runs_app_spec_id_fkey" FOREIGN KEY ("app_spec_id") REFERENCES "public"."app_specs"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."factory_runs"
    ADD CONSTRAINT "factory_runs_base_factory_run_id_fkey" FOREIGN KEY ("base_factory_run_id") REFERENCES "public"."factory_runs"("id");



ALTER TABLE ONLY "public"."factory_runs"
    ADD CONSTRAINT "factory_runs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."factory_runs"
    ADD CONSTRAINT "factory_runs_requested_by_fkey" FOREIGN KEY ("requested_by") REFERENCES "auth"."users"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."factory_runs"
    ADD CONSTRAINT "factory_runs_workflow_id_fkey" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."generated_artifacts"
    ADD CONSTRAINT "generated_artifacts_build_step_id_fkey" FOREIGN KEY ("build_step_id") REFERENCES "public"."build_steps"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."generated_artifacts"
    ADD CONSTRAINT "generated_artifacts_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."generated_artifacts"
    ADD CONSTRAINT "generated_artifacts_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."jobs"
    ADD CONSTRAINT "jobs_workflow_id_fkey" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."module_registry"
    ADD CONSTRAINT "module_registry_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."module_registry"
    ADD CONSTRAINT "module_registry_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organization_members"
    ADD CONSTRAINT "organization_members_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organization_members"
    ADD CONSTRAINT "organization_members_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."organizations"
    ADD CONSTRAINT "organizations_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_members"
    ADD CONSTRAINT "project_members_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."project_members"
    ADD CONSTRAINT "project_members_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."release_gates"
    ADD CONSTRAINT "release_gates_checked_by_fkey" FOREIGN KEY ("checked_by") REFERENCES "auth"."users"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."release_gates"
    ADD CONSTRAINT "release_gates_factory_run_id_fkey" FOREIGN KEY ("factory_run_id") REFERENCES "public"."factory_runs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."release_gates"
    ADD CONSTRAINT "release_gates_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."spec_compilations"
    ADD CONSTRAINT "spec_compilations_app_spec_id_fkey" FOREIGN KEY ("app_spec_id") REFERENCES "public"."app_specs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."spec_compilations"
    ADD CONSTRAINT "spec_compilations_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."spec_compilations"
    ADD CONSTRAINT "spec_compilations_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."support_requests"
    ADD CONSTRAINT "support_requests_customer_account_id_fkey" FOREIGN KEY ("customer_account_id") REFERENCES "public"."customer_accounts"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."support_requests"
    ADD CONSTRAINT "support_requests_opened_by_fkey" FOREIGN KEY ("opened_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."system_roles"
    ADD CONSTRAINT "system_roles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."workflows"
    ADD CONSTRAINT "workflows_app_spec_id_fkey" FOREIGN KEY ("app_spec_id") REFERENCES "public"."app_specs"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."workflows"
    ADD CONSTRAINT "workflows_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."workflows"
    ADD CONSTRAINT "workflows_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE CASCADE;



ALTER TABLE "private"."app_compiler_audit" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."app_launch_audit" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."assisted_build_cost_policy" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."builder_certification_golden_profiles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."builder_release_gate_profiles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."builder_route_decisions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."capability_adapter_evidence" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."capability_adapter_registry" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."capability_adapter_results" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."factory_execution_events" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."internal_usage_audit" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."internal_usage_ledger" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."internal_usage_overrides" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."internal_usage_policy" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."launch_readiness_checks" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."notification_events" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."notification_outbox" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."notification_production_activations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."notification_reconciliation_checks" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."operational_incidents" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."payment_fulfillment_events" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."payment_production_fulfillment_events" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."payment_production_orders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."payment_production_webhook_events" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."payment_reconciliation_checks" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."payment_sandbox_orders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."payment_webhook_events" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."production_adapter_registry" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."production_deployment_verifications" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."production_promotion_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."production_rollback_audits" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."release_validation_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."runner_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "private"."usage_counters" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."app_specs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "app_specs_insert_builder" ON "public"."app_specs" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("created_by" = ( SELECT "auth"."uid"() AS "uid"))));



CREATE POLICY "app_specs_select_member" ON "public"."app_specs" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "app_specs_update_builder" ON "public"."app_specs" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



ALTER TABLE "public"."approvals" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "approvals_insert_builder" ON "public"."approvals" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("requested_by" = ( SELECT "auth"."uid"() AS "uid"))));



CREATE POLICY "approvals_select_member" ON "public"."approvals" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "approvals_update_reviewer" ON "public"."approvals" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'reviewer'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'reviewer'::"text"]));



ALTER TABLE "public"."audit_logs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "audit_logs_insert_member" ON "public"."audit_logs" FOR INSERT TO "authenticated" WITH CHECK ((("actor_user_id" = ( SELECT "auth"."uid"() AS "uid")) AND ((("project_id" IS NOT NULL) AND "private"."is_project_member"("project_id")) OR (("project_id" IS NULL) AND ("organization_id" IS NOT NULL) AND "private"."is_org_member"("organization_id")))));



CREATE POLICY "audit_logs_select_member" ON "public"."audit_logs" FOR SELECT TO "authenticated" USING (((("project_id" IS NOT NULL) AND "private"."is_project_member"("project_id")) OR (("project_id" IS NULL) AND ("organization_id" IS NOT NULL) AND "private"."is_org_member"("organization_id"))));



ALTER TABLE "public"."build_failure_events" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "build_failure_events_member_insert" ON "public"."build_failure_events" FOR INSERT TO "authenticated" WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "build_failure_events"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



CREATE POLICY "build_failure_events_member_read" ON "public"."build_failure_events" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "build_failure_events"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



CREATE POLICY "build_failure_events_member_update" ON "public"."build_failure_events" FOR UPDATE TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "build_failure_events"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid")))))) WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "build_failure_events"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."build_steps" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "build_steps_insert_builder" ON "public"."build_steps" FOR INSERT TO "authenticated" WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



CREATE POLICY "build_steps_select_member" ON "public"."build_steps" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "build_steps_update_builder" ON "public"."build_steps" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



CREATE POLICY "builder_cert_evidence_insert" ON "public"."builder_certification_evidence" FOR INSERT TO "authenticated" WITH CHECK ((("project_id" IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "builder_certification_evidence"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid")))))));



CREATE POLICY "builder_cert_evidence_read" ON "public"."builder_certification_evidence" FOR SELECT TO "authenticated" USING ((("project_id" IS NULL) OR (EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "builder_certification_evidence"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid")))))));



ALTER TABLE "public"."builder_certification_evidence" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."builder_certification_policies" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "builder_certification_policies_read" ON "public"."builder_certification_policies" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."builder_certification_results" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "builder_certification_results_read" ON "public"."builder_certification_results" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."builder_registry" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "builder_registry_read" ON "public"."builder_registry" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."ci_evidence_ingestions" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "ci_evidence_ingestions_insert_project" ON "public"."ci_evidence_ingestions" FOR INSERT TO "authenticated" WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "ci_evidence_ingestions"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



CREATE POLICY "ci_evidence_ingestions_select_project" ON "public"."ci_evidence_ingestions" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "ci_evidence_ingestions"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."ci_repair_actions" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "ci_repair_actions_insert_project" ON "public"."ci_repair_actions" FOR INSERT TO "authenticated" WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "ci_repair_actions"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



CREATE POLICY "ci_repair_actions_select_project" ON "public"."ci_repair_actions" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "ci_repair_actions"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



CREATE POLICY "ci_repair_actions_update_project" ON "public"."ci_repair_actions" FOR UPDATE TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "ci_repair_actions"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid")))))) WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."project_members" "pm"
  WHERE (("pm"."project_id" = "ci_repair_actions"."project_id") AND ("pm"."user_id" = ( SELECT "auth"."uid"() AS "uid"))))));



ALTER TABLE "public"."customer_accounts" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "customer_accounts_insert_own" ON "public"."customer_accounts" FOR INSERT TO "authenticated" WITH CHECK (("owner_user_id" = ( SELECT "auth"."uid"() AS "uid")));



CREATE POLICY "customer_accounts_select_own" ON "public"."customer_accounts" FOR SELECT TO "authenticated" USING (("owner_user_id" = ( SELECT "auth"."uid"() AS "uid")));



CREATE POLICY "customer_accounts_update_own" ON "public"."customer_accounts" FOR UPDATE TO "authenticated" USING (("owner_user_id" = ( SELECT "auth"."uid"() AS "uid"))) WITH CHECK (("owner_user_id" = ( SELECT "auth"."uid"() AS "uid")));



ALTER TABLE "public"."deployments" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "deployments_insert_builder" ON "public"."deployments" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("created_by" = ( SELECT "auth"."uid"() AS "uid"))));



CREATE POLICY "deployments_select_member" ON "public"."deployments" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "deployments_update_reviewer" ON "public"."deployments" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'reviewer'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'reviewer'::"text"]));



ALTER TABLE "public"."environments" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "environments_delete_admin" ON "public"."environments" FOR DELETE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "environments_insert_builder" ON "public"."environments" FOR INSERT TO "authenticated" WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



CREATE POLICY "environments_select_member" ON "public"."environments" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "environments_update_builder" ON "public"."environments" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



ALTER TABLE "public"."factory_artifacts" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "factory_artifacts_delete_admin" ON "public"."factory_artifacts" FOR DELETE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "factory_artifacts_insert_builder" ON "public"."factory_artifacts" FOR INSERT TO "authenticated" WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



CREATE POLICY "factory_artifacts_select_member" ON "public"."factory_artifacts" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "factory_artifacts_update_builder" ON "public"."factory_artifacts" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



ALTER TABLE "public"."factory_runs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "factory_runs_delete_admin" ON "public"."factory_runs" FOR DELETE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "factory_runs_insert_builder" ON "public"."factory_runs" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("requested_by" = ( SELECT "auth"."uid"() AS "uid")) AND (("target_environment" <> 'production'::"text") OR ("production_locked" = true))));



CREATE POLICY "factory_runs_select_member" ON "public"."factory_runs" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "factory_runs_update_builder" ON "public"."factory_runs" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND (("target_environment" <> 'production'::"text") OR ("production_locked" = true))));



ALTER TABLE "public"."generated_artifacts" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "generated_artifacts_delete_admin" ON "public"."generated_artifacts" FOR DELETE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "generated_artifacts_insert_builder" ON "public"."generated_artifacts" FOR INSERT TO "authenticated" WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



CREATE POLICY "generated_artifacts_select_member" ON "public"."generated_artifacts" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "generated_artifacts_update_builder" ON "public"."generated_artifacts" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



ALTER TABLE "public"."jobs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "jobs_delete_admin" ON "public"."jobs" FOR DELETE TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."workflows" "w"
  WHERE (("w"."id" = "jobs"."workflow_id") AND "private"."has_project_role"("w"."project_id", ARRAY['owner'::"text", 'admin'::"text"])))));



CREATE POLICY "jobs_insert_builder" ON "public"."jobs" FOR INSERT TO "authenticated" WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."workflows" "w"
  WHERE (("w"."id" = "jobs"."workflow_id") AND "private"."has_project_role"("w"."project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])))));



CREATE POLICY "jobs_select_member" ON "public"."jobs" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."workflows" "w"
  WHERE (("w"."id" = "jobs"."workflow_id") AND "private"."is_project_member"("w"."project_id")))));



CREATE POLICY "jobs_update_builder" ON "public"."jobs" FOR UPDATE TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."workflows" "w"
  WHERE (("w"."id" = "jobs"."workflow_id") AND "private"."has_project_role"("w"."project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]))))) WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."workflows" "w"
  WHERE (("w"."id" = "jobs"."workflow_id") AND "private"."has_project_role"("w"."project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])))));



ALTER TABLE "public"."module_registry" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "module_registry_delete_admin" ON "public"."module_registry" FOR DELETE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "module_registry_insert_builder" ON "public"."module_registry" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("created_by" = ( SELECT "auth"."uid"() AS "uid"))));



CREATE POLICY "module_registry_select_member" ON "public"."module_registry" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "module_registry_update_builder" ON "public"."module_registry" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



ALTER TABLE "public"."organization_members" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "organization_members_delete_admin" ON "public"."organization_members" FOR DELETE TO "authenticated" USING ("private"."has_org_role"("organization_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "organization_members_insert_admin" ON "public"."organization_members" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_org_role"("organization_id", ARRAY['owner'::"text", 'admin'::"text"]) OR (("user_id" = ( SELECT "auth"."uid"() AS "uid")) AND ("role" = 'owner'::"text") AND (EXISTS ( SELECT 1
   FROM "public"."organizations" "o"
  WHERE (("o"."id" = "organization_members"."organization_id") AND ("o"."created_by" = ( SELECT "auth"."uid"() AS "uid"))))))));



CREATE POLICY "organization_members_select_member" ON "public"."organization_members" FOR SELECT TO "authenticated" USING ("private"."is_org_member"("organization_id"));



CREATE POLICY "organization_members_update_admin" ON "public"."organization_members" FOR UPDATE TO "authenticated" USING ("private"."has_org_role"("organization_id", ARRAY['owner'::"text", 'admin'::"text"])) WITH CHECK ("private"."has_org_role"("organization_id", ARRAY['owner'::"text", 'admin'::"text"]));



ALTER TABLE "public"."organizations" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "organizations_insert_creator" ON "public"."organizations" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "created_by"));



CREATE POLICY "organizations_select_member" ON "public"."organizations" FOR SELECT TO "authenticated" USING ("private"."is_org_member"("id"));



CREATE POLICY "organizations_update_admin" ON "public"."organizations" FOR UPDATE TO "authenticated" USING ("private"."has_org_role"("id", ARRAY['owner'::"text", 'admin'::"text"])) WITH CHECK ("private"."has_org_role"("id", ARRAY['owner'::"text", 'admin'::"text"]));



ALTER TABLE "public"."plan_catalog" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "plan_catalog_public_read" ON "public"."plan_catalog" FOR SELECT TO "authenticated", "anon" USING (("is_public" = true));



ALTER TABLE "public"."profiles" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "profiles_insert_self" ON "public"."profiles" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "profiles_select_self" ON "public"."profiles" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "profiles_update_self" ON "public"."profiles" FOR UPDATE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id")) WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



ALTER TABLE "public"."project_members" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "project_members_delete_admin" ON "public"."project_members" FOR DELETE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "project_members_insert_admin" ON "public"."project_members" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]) OR (("user_id" = ( SELECT "auth"."uid"() AS "uid")) AND ("role" = 'owner'::"text") AND (EXISTS ( SELECT 1
   FROM "public"."projects" "p"
  WHERE (("p"."id" = "project_members"."project_id") AND ("p"."created_by" = ( SELECT "auth"."uid"() AS "uid"))))))));



CREATE POLICY "project_members_select_member" ON "public"."project_members" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "project_members_update_admin" ON "public"."project_members" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



ALTER TABLE "public"."projects" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "projects_insert_builder" ON "public"."projects" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_org_role"("organization_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("created_by" = ( SELECT "auth"."uid"() AS "uid"))));



CREATE POLICY "projects_select_member" ON "public"."projects" FOR SELECT TO "authenticated" USING ("private"."is_org_member"("organization_id"));



CREATE POLICY "projects_update_admin" ON "public"."projects" FOR UPDATE TO "authenticated" USING ("private"."has_org_role"("organization_id", ARRAY['owner'::"text", 'admin'::"text"])) WITH CHECK ("private"."has_org_role"("organization_id", ARRAY['owner'::"text", 'admin'::"text"]));



ALTER TABLE "public"."reference_saas_templates" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "reference_saas_templates_select_authenticated" ON "public"."reference_saas_templates" FOR SELECT TO "authenticated" USING (("status" = 'active'::"text"));



ALTER TABLE "public"."release_gates" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "release_gates_delete_admin" ON "public"."release_gates" FOR DELETE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text"]));



CREATE POLICY "release_gates_insert_builder" ON "public"."release_gates" FOR INSERT TO "authenticated" WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text", 'reviewer'::"text"]));



CREATE POLICY "release_gates_select_member" ON "public"."release_gates" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "release_gates_update_reviewer" ON "public"."release_gates" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'reviewer'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'reviewer'::"text"]));



ALTER TABLE "public"."repair_recipe_registry" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "repair_recipe_registry_read" ON "public"."repair_recipe_registry" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."spec_compilations" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "spec_compilations_insert_builder" ON "public"."spec_compilations" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("created_by" = ( SELECT "auth"."uid"() AS "uid"))));



CREATE POLICY "spec_compilations_select_member" ON "public"."spec_compilations" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "spec_compilations_update_builder" ON "public"."spec_compilations" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));



ALTER TABLE "public"."support_requests" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "support_requests_insert_own" ON "public"."support_requests" FOR INSERT TO "authenticated" WITH CHECK ((("opened_by" = ( SELECT "auth"."uid"() AS "uid")) AND (EXISTS ( SELECT 1
   FROM "public"."customer_accounts" "ca"
  WHERE (("ca"."id" = "support_requests"."customer_account_id") AND ("ca"."owner_user_id" = ( SELECT "auth"."uid"() AS "uid")))))));



CREATE POLICY "support_requests_select_own" ON "public"."support_requests" FOR SELECT TO "authenticated" USING (("opened_by" = ( SELECT "auth"."uid"() AS "uid")));



ALTER TABLE "public"."system_roles" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "system_roles_select_self" ON "public"."system_roles" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



ALTER TABLE "public"."vl_cert_health" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "vl_cert_health_read" ON "public"."vl_cert_health" FOR SELECT TO "authenticated", "anon" USING (("id" = 1));



ALTER TABLE "public"."workflows" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "workflows_insert_builder" ON "public"."workflows" FOR INSERT TO "authenticated" WITH CHECK (("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]) AND ("created_by" = ( SELECT "auth"."uid"() AS "uid"))));



CREATE POLICY "workflows_select_member" ON "public"."workflows" FOR SELECT TO "authenticated" USING ("private"."is_project_member"("project_id"));



CREATE POLICY "workflows_update_builder" ON "public"."workflows" FOR UPDATE TO "authenticated" USING ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"])) WITH CHECK ("private"."has_project_role"("project_id", ARRAY['owner'::"text", 'admin'::"text", 'builder'::"text"]));





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "private" TO "authenticated";
GRANT USAGE ON SCHEMA "private" TO "service_role";



GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";















































































































































































































REVOKE ALL ON FUNCTION "private"."acp_admin_event_id"("p_action_id" "text", "p_event_type" "text") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."acp_append_admin_audit_event"("p_action_id" "text", "p_event_type" "text", "p_capability" "text", "p_scope" "jsonb", "p_input_digest" "text", "p_decision" "text", "p_reason_code" "text", "p_execution_status" "text", "p_result_digest" "text", "p_metadata" "jsonb", "p_actor_evidence" "jsonb") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."acp_assert_actor_evidence"("p_evidence" "jsonb") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."acp_read_agent_grant_chain_nonprod_impl"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."acp_read_agent_grant_chain_nonprod_impl"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") TO "service_role";



REVOKE ALL ON FUNCTION "private"."activate_approved_notification_production"() FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."activate_approved_notification_production"() TO "service_role";



REVOKE ALL ON FUNCTION "private"."activate_notification_adapter_if_approved"() FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."activate_notification_adapter_if_approved"() TO "service_role";



REVOKE ALL ON FUNCTION "private"."apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) TO "service_role";



REVOKE ALL ON FUNCTION "private"."apply_resend_sandbox_webhook"("p_event_key" "text", "p_provider_message_id" "text", "p_event_type" "text", "p_status" "text", "p_payload_sha256" "text") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."approve_and_launch_app_spec"("p_app_spec_id" "uuid", "p_approver_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."approve_and_launch_app_spec"("p_app_spec_id" "uuid", "p_approver_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."approve_notification_production_activation"("p_rationale" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."approve_notification_production_activation"("p_rationale" "text") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."approve_production_release"("p_deployment_id" "uuid", "p_rationale" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."approve_production_release"("p_deployment_id" "uuid", "p_rationale" "text") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."auto_prepare_release_candidate"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."begin_factory_validation"("p_factory_run_id" "uuid", "p_build_result" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."begin_factory_validation"("p_factory_run_id" "uuid", "p_build_result" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."billplz_production_readiness"() FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."billplz_production_readiness"() TO "service_role";



REVOKE ALL ON FUNCTION "private"."block_agent_audit_mutation"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."build_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."build_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "private"."build_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."claim_operational_alert_job"("p_runner_identity" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."claim_operational_alert_job"("p_runner_identity" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."compile_app_request"("p_prompt" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."compile_app_request"("p_prompt" "text") TO "service_role";



REVOKE ALL ON FUNCTION "private"."complete_factory_validation"("p_factory_run_id" "uuid", "p_pass" boolean, "p_qa" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."complete_factory_validation"("p_factory_run_id" "uuid", "p_pass" boolean, "p_qa" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."complete_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text", "p_error_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."complete_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text", "p_error_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "private"."create_app_spec_revision"("p_base_app_spec_id" "uuid", "p_change_request" "text", "p_actor" "uuid") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enforce_approved_app_spec_for_factory_run"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enforce_assisted_build_execution_gate"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enforce_deployment_snapshot_immutability"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enforce_production_deployment_guard"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enforce_public_factory_quota"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enforce_release_identity_binding"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enqueue_factory_runner_job"() FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."enqueue_factory_runner_job"() TO "service_role";



REVOKE ALL ON FUNCTION "private"."enqueue_production_promotion_job"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enqueue_release_validation_job"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."enrich_factory_run_capability_plan"() FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."enrich_factory_run_capability_plan"() TO "service_role";



REVOKE ALL ON FUNCTION "private"."ensure_default_project_environments"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."ensure_release_candidate"("p_factory_run_id" "uuid", "p_actor" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."ensure_release_candidate"("p_factory_run_id" "uuid", "p_actor" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."evaluate_factory_preflight"("p_compilation_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."evaluate_factory_preflight"("p_compilation_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."fulfill_verified_sandbox_payment"("p_order_id" "uuid", "p_action_key" "text") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."get_deployment_required_release_gates"("p_deployment_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."get_deployment_required_release_gates"("p_deployment_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."get_required_release_gates"("p_factory_run_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."get_required_release_gates"("p_factory_run_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."guard_customer_account_mutation"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."has_org_role"("p_org" "uuid", "p_roles" "text"[], "p_user" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."has_org_role"("p_org" "uuid", "p_roles" "text"[], "p_user" "uuid") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."has_project_role"("p_project" "uuid", "p_roles" "text"[], "p_user" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."has_project_role"("p_project" "uuid", "p_roles" "text"[], "p_user" "uuid") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."is_org_member"("p_org" "uuid", "p_user" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."is_org_member"("p_org" "uuid", "p_user" "uuid") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."is_project_member"("p_project" "uuid", "p_user" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."is_project_member"("p_project" "uuid", "p_user" "uuid") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."mark_factory_build_started"("p_factory_run_id" "uuid", "p_adapter_metadata" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."mark_factory_build_started"("p_factory_run_id" "uuid", "p_adapter_metadata" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."notification_production_readiness"() FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."notification_production_readiness"() TO "service_role";



REVOKE ALL ON FUNCTION "private"."prepare_factory_execution"("p_factory_run_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."prepare_factory_execution"("p_factory_run_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."prepare_release_candidate"("p_factory_run_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."prepare_release_candidate"("p_factory_run_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "private"."prepare_release_candidate"("p_factory_run_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."reconcile_notification_outbox"("p_outbox_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."reconcile_notification_outbox"("p_outbox_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."record_factory_artifact"("p_factory_run_id" "uuid", "p_artifact_type" "text", "p_name" "text", "p_storage_path" "text", "p_sha256" "text", "p_metadata" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."record_factory_artifact"("p_factory_run_id" "uuid", "p_artifact_type" "text", "p_name" "text", "p_storage_path" "text", "p_sha256" "text", "p_metadata" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."reject_generated_artifact_secrets"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."reject_production_release"("p_deployment_id" "uuid", "p_rationale" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."reject_production_release"("p_deployment_id" "uuid", "p_rationale" "text") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."request_production_rollback"("p_deployment_id" "uuid", "p_reason" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."request_production_rollback"("p_deployment_id" "uuid", "p_reason" "text") TO "authenticated";



REVOKE ALL ON FUNCTION "private"."request_vrs_internal_usage_override_impl"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."request_vrs_internal_usage_override_impl"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer) FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."resolve_capability_adapter_plan"("p_normalized_spec" "jsonb", "p_module_plan" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."resolve_capability_adapter_plan"("p_normalized_spec" "jsonb", "p_module_plan" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."resolve_factory_builder"("p_factory_run_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."resolve_factory_builder"("p_factory_run_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "private"."route_builder"("p_builder_type" "text", "p_target" "text", "p_required_capabilities" "text"[]) FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."route_builder"("p_builder_type" "text", "p_target" "text", "p_required_capabilities" "text"[]) TO "service_role";



REVOKE ALL ON FUNCTION "private"."seed_factory_additional_sources"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."seed_factory_sources"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."seed_upgrade_source_from_base"("p_upgrade_run_id" "uuid", "p_base_run_id" "uuid", "p_change_request" "text") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."set_spec_compilation_capability_plan"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."validate_agent_audit_chain"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."validate_agent_capability_grant"() FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."validate_product_alignment"("p_alignment" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "private"."validate_product_alignment"("p_alignment" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "private"."validate_product_alignment"("p_alignment" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "private"."vl_get_assisted_build_quote_impl"("p_complexity" "text") FROM PUBLIC;



REVOKE ALL ON FUNCTION "private"."vl_prepare_assisted_build_product_alignment_impl"("p_answers" "jsonb", "p_structured" "jsonb") FROM PUBLIC;



REVOKE ALL ON FUNCTION "public"."acp_delegate_agent_grant_nonprod"("p_action_id" "text", "p_parent_grant_id" "uuid", "p_agent_id" "text", "p_agent_version" "text", "p_role_name" "text", "p_capabilities" "text"[], "p_scope" "jsonb", "p_budget" "jsonb", "p_valid_from" timestamp with time zone, "p_valid_until" timestamp with time zone, "p_actor_evidence" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."acp_delegate_agent_grant_nonprod"("p_action_id" "text", "p_parent_grant_id" "uuid", "p_agent_id" "text", "p_agent_version" "text", "p_role_name" "text", "p_capabilities" "text"[], "p_scope" "jsonb", "p_budget" "jsonb", "p_valid_from" timestamp with time zone, "p_valid_until" timestamp with time zone, "p_actor_evidence" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."acp_read_agent_grant_chain_nonprod"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."acp_read_agent_grant_chain_nonprod"("p_grant_id" "uuid", "p_agent_id" "text", "p_project_id" "text", "p_target_environment" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."acp_revoke_agent_grant"("p_action_id" "text", "p_grant_id" "uuid", "p_reason" "text", "p_actor_evidence" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."acp_revoke_agent_grant"("p_action_id" "text", "p_grant_id" "uuid", "p_reason" "text", "p_actor_evidence" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."approve_vrs_notification_production_activation"("p_rationale" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."approve_vrs_notification_production_activation"("p_rationale" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."approve_vrs_notification_production_activation"("p_rationale" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."approve_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."approve_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."approve_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."bootstrap_reference_saas"("p_template_key" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."bootstrap_reference_saas"("p_template_key" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."bootstrap_reference_saas"("p_template_key" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."claim_vrs_experimental_runner_job"("p_runner_identity" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."claim_vrs_experimental_runner_job"("p_runner_identity" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."claim_vrs_operational_alert_job"("p_runner_identity" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."claim_vrs_operational_alert_job"("p_runner_identity" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."claim_vrs_production_promotion_job"("p_runner_identity" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."claim_vrs_production_promotion_job"("p_runner_identity" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."claim_vrs_production_rollback_job"("p_runner_identity" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."claim_vrs_production_rollback_job"("p_runner_identity" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."claim_vrs_release_validation_job"("p_runner_identity" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."claim_vrs_release_validation_job"("p_runner_identity" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."claim_vrs_runner_job"("p_runner_identity" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."claim_vrs_runner_job"("p_runner_identity" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."complete_vrs_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text", "p_error_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."complete_vrs_operational_alert_job"("p_incident_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_provider_message_id" "text", "p_error_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."complete_vrs_production_promotion_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."complete_vrs_production_promotion_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."complete_vrs_production_rollback_job"("p_rollback_audit_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."complete_vrs_production_rollback_job"("p_rollback_audit_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."complete_vrs_release_validation_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_gate_results" "jsonb", "p_result" "jsonb", "p_error_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."complete_vrs_release_validation_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_gate_results" "jsonb", "p_result" "jsonb", "p_error_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."complete_vrs_runner_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."complete_vrs_runner_job"("p_job_id" "uuid", "p_lease_token" "uuid", "p_success" boolean, "p_result" "jsonb", "p_error_text" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."create_organization_with_owner"("p_name" "text", "p_slug" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."create_organization_with_owner"("p_name" "text", "p_slug" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."create_organization_with_owner"("p_name" "text", "p_slug" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."create_project_with_owner"("p_organization_id" "uuid", "p_name" "text", "p_slug" "text", "p_description" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."create_project_with_owner"("p_organization_id" "uuid", "p_name" "text", "p_slug" "text", "p_description" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."create_project_with_owner"("p_organization_id" "uuid", "p_name" "text", "p_slug" "text", "p_description" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."enqueue_vrs_golden_certification_runs"("p_builder_key" "text", "p_run_count" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."enqueue_vrs_golden_certification_runs"("p_builder_key" "text", "p_run_count" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."evaluate_builder_certification"("p_builder_key" "text", "p_activate" boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."evaluate_builder_certification"("p_builder_key" "text", "p_activate" boolean) TO "service_role";



REVOKE ALL ON FUNCTION "public"."evaluate_vrs_release_server_gates"("p_factory_run_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."evaluate_vrs_release_server_gates"("p_factory_run_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."get_vrs_billplz_production_readiness"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."get_vrs_billplz_production_readiness"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."get_vrs_notification_production_readiness"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."get_vrs_notification_production_readiness"() TO "service_role";



GRANT ALL ON FUNCTION "public"."guard_builder_activation"() TO "anon";
GRANT ALL ON FUNCTION "public"."guard_builder_activation"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."guard_builder_activation"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."harvest_exact_release_gate_certification_evidence"("p_factory_run_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."harvest_exact_release_gate_certification_evidence"("p_factory_run_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."ingest_ci_evidence"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_external_run_id" "text", "p_external_job_id" "text", "p_head_sha" "text", "p_run_status" "text", "p_run_conclusion" "text", "p_step_results" "jsonb", "p_artifact_results" "jsonb", "p_raw_summary" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."ingest_ci_evidence"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_external_run_id" "text", "p_external_job_id" "text", "p_head_sha" "text", "p_run_status" "text", "p_run_conclusion" "text", "p_step_results" "jsonb", "p_artifact_results" "jsonb", "p_raw_summary" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."learn_from_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."learn_from_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."mark_ci_repair_applied"("p_action_id" "uuid", "p_execution_result" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."mark_ci_repair_applied"("p_action_id" "uuid", "p_execution_result" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."mark_ci_repair_applied"("p_action_id" "uuid", "p_execution_result" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."mark_ci_repair_retry"("p_action_id" "uuid", "p_retry_run_id" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."mark_ci_repair_retry"("p_action_id" "uuid", "p_retry_run_id" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."mark_ci_repair_retry"("p_action_id" "uuid", "p_retry_run_id" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."propose_ci_repair"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_branch" "text", "p_failure_class" "text", "p_signature" "text", "p_error_text" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."propose_ci_repair"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_branch" "text", "p_failure_class" "text", "p_signature" "text", "p_error_text" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."propose_ci_repair"("p_project_id" "uuid", "p_factory_run_id" "uuid", "p_builder_key" "text", "p_repository" "text", "p_branch" "text", "p_failure_class" "text", "p_signature" "text", "p_error_text" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."reconcile_factory_artifact_physical_provenance"("p_factory_run_id" "uuid", "p_github_run_id" "text", "p_github_artifact_id" "text", "p_github_artifact_digest" "text", "p_github_head_sha" "text", "p_github_artifact_expires_at" timestamp with time zone, "p_artifact_name" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."reconcile_factory_artifact_physical_provenance"("p_factory_run_id" "uuid", "p_github_run_id" "text", "p_github_artifact_id" "text", "p_github_artifact_digest" "text", "p_github_head_sha" "text", "p_github_artifact_expires_at" timestamp with time zone, "p_artifact_name" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."record_vrs_supply_chain_attestation"("p_factory_run_id" "uuid", "p_artifact_sha256" "text", "p_github_run_id" "text", "p_build_workflow_run_id" "text", "p_provenance_verified" boolean, "p_sbom_verified" boolean, "p_sbom_sha256" "text", "p_evidence" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."record_vrs_supply_chain_attestation"("p_factory_run_id" "uuid", "p_artifact_sha256" "text", "p_github_run_id" "text", "p_build_workflow_run_id" "text", "p_provenance_verified" boolean, "p_sbom_verified" boolean, "p_sbom_sha256" "text", "p_evidence" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."recover_exhausted_certification_depth_validation"("p_factory_run_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."recover_exhausted_certification_depth_validation"("p_factory_run_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."reject_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."reject_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."reject_vrs_production_release"("p_deployment_id" "uuid", "p_rationale" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."request_vrs_internal_usage_override"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."request_vrs_internal_usage_override"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."request_vrs_internal_usage_override"("p_project_id" "uuid", "p_reason" "text", "p_duration_minutes" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."request_vrs_production_rollback"("p_deployment_id" "uuid", "p_reason" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."request_vrs_production_rollback"("p_deployment_id" "uuid", "p_reason" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."request_vrs_production_rollback"("p_deployment_id" "uuid", "p_reason" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."touch_updated_at"() FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."touch_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."touch_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."touch_updated_at"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."verify_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."verify_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."verify_ci_repair"("p_action_id" "uuid", "p_success" boolean, "p_details" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_apply_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_apply_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_apply_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_apply_resend_sandbox_webhook"("p_event_key" "text", "p_provider_message_id" "text", "p_event_type" "text", "p_status" "text", "p_payload_sha256" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_apply_resend_sandbox_webhook"("p_event_key" "text", "p_provider_message_id" "text", "p_event_type" "text", "p_status" "text", "p_payload_sha256" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_billplz_ci_mark_cancelled"("p_order_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_billplz_ci_mark_cancelled"("p_order_id" "uuid") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_billplz_ci_record_order"("p_provider_bill_id" "text", "p_merchant_reference" "text", "p_checkout_url" "text", "p_github_run_id" "text", "p_github_sha" "text", "p_workflow_ref" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_billplz_ci_record_order"("p_provider_bill_id" "text", "p_merchant_reference" "text", "p_checkout_url" "text", "p_github_run_id" "text", "p_github_sha" "text", "p_workflow_ref" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_billplz_ci_record_reconciliation"("p_order_id" "uuid", "p_provider_bill_id" "text", "p_provider_status" "text", "p_provider_amount_minor" integer, "p_provider_http_status" integer, "p_paid" boolean, "p_pass" boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_billplz_ci_record_reconciliation"("p_order_id" "uuid", "p_provider_bill_id" "text", "p_provider_status" "text", "p_provider_amount_minor" integer, "p_provider_http_status" integer, "p_paid" boolean, "p_pass" boolean) TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_fulfill_verified_sandbox_payment"("p_order_id" "uuid", "p_action_key" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_fulfill_verified_sandbox_payment"("p_order_id" "uuid", "p_action_key" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_get_assisted_build_quote"("p_complexity" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_get_assisted_build_quote"("p_complexity" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."vl_get_assisted_build_quote"("p_complexity" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_prepare_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_prepare_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."vl_prepare_assisted_build_product_alignment"("p_answers" "jsonb", "p_structured" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_record_invalid_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_record_invalid_billplz_production_test_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_record_invalid_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_record_invalid_billplz_sandbox_webhook"("p_event_key" "text", "p_provider_bill_id" "text", "p_payload_sha256" "text", "p_normalized_status" "text", "p_amount_minor" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_resend_reconciliation_source_check"("p_provider_message_id" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_resend_reconciliation_source_check"("p_provider_message_id" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."vl_resend_record_sandbox_send"("p_recipient_hash" "text", "p_subject" "text", "p_provider_message_id" "text", "p_idempotency_key" "text", "p_created_by" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."vl_resend_record_sandbox_send"("p_recipient_hash" "text", "p_subject" "text", "p_provider_message_id" "text", "p_idempotency_key" "text", "p_created_by" "uuid") TO "service_role";


















GRANT SELECT,INSERT ON TABLE "private"."app_compiler_audit" TO "service_role";



GRANT SELECT,INSERT ON TABLE "private"."app_launch_audit" TO "service_role";



GRANT SELECT ON TABLE "private"."assisted_build_quote_catalog" TO "authenticated";



GRANT SELECT ON TABLE "private"."builder_release_gate_profiles" TO "service_role";



GRANT SELECT,INSERT ON TABLE "private"."builder_route_decisions" TO "service_role";



GRANT ALL ON TABLE "private"."capability_adapter_evidence" TO "service_role";



GRANT ALL ON TABLE "private"."capability_adapter_registry" TO "service_role";



GRANT ALL ON TABLE "private"."capability_adapter_results" TO "service_role";



GRANT SELECT,INSERT ON TABLE "private"."factory_execution_events" TO "service_role";



GRANT INSERT("project_id") ON TABLE "private"."internal_usage_override_request" TO "authenticated";



GRANT INSERT("reason") ON TABLE "private"."internal_usage_override_request" TO "authenticated";



GRANT INSERT("duration_minutes") ON TABLE "private"."internal_usage_override_request" TO "authenticated";



GRANT SELECT("result") ON TABLE "private"."internal_usage_override_request" TO "authenticated";



GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "private"."notification_events" TO "service_role";



GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "private"."notification_outbox" TO "service_role";



GRANT SELECT,INSERT,UPDATE ON TABLE "private"."notification_production_activations" TO "service_role";



GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "private"."notification_reconciliation_checks" TO "service_role";



GRANT ALL ON TABLE "private"."payment_production_fulfillment_events" TO "service_role";



GRANT ALL ON TABLE "private"."payment_production_orders" TO "service_role";



GRANT ALL ON TABLE "private"."payment_production_webhook_events" TO "service_role";



GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "private"."payment_reconciliation_checks" TO "service_role";



GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "private"."payment_sandbox_orders" TO "service_role";



GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "private"."payment_webhook_events" TO "service_role";



GRANT SELECT ON TABLE "private"."product_alignment_policy" TO "service_role";



GRANT SELECT ON TABLE "private"."production_adapter_registry" TO "service_role";



GRANT SELECT,INSERT,UPDATE ON TABLE "private"."production_promotion_jobs" TO "service_role";



GRANT SELECT,INSERT,UPDATE ON TABLE "private"."release_validation_jobs" TO "service_role";



GRANT SELECT,INSERT,UPDATE ON TABLE "private"."runner_jobs" TO "service_role";



GRANT ALL ON TABLE "public"."app_specs" TO "anon";
GRANT ALL ON TABLE "public"."app_specs" TO "authenticated";
GRANT ALL ON TABLE "public"."app_specs" TO "service_role";



GRANT SELECT,MAINTAIN ON TABLE "public"."approvals" TO "anon";
GRANT SELECT,MAINTAIN ON TABLE "public"."approvals" TO "authenticated";
GRANT ALL ON TABLE "public"."approvals" TO "service_role";



GRANT ALL ON TABLE "public"."audit_logs" TO "anon";
GRANT ALL ON TABLE "public"."audit_logs" TO "authenticated";
GRANT ALL ON TABLE "public"."audit_logs" TO "service_role";



GRANT ALL ON SEQUENCE "public"."audit_logs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."audit_logs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."audit_logs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."build_failure_events" TO "anon";
GRANT ALL ON TABLE "public"."build_failure_events" TO "authenticated";
GRANT ALL ON TABLE "public"."build_failure_events" TO "service_role";



GRANT ALL ON TABLE "public"."build_steps" TO "anon";
GRANT ALL ON TABLE "public"."build_steps" TO "authenticated";
GRANT ALL ON TABLE "public"."build_steps" TO "service_role";



GRANT ALL ON TABLE "public"."builder_certification_evidence" TO "anon";
GRANT ALL ON TABLE "public"."builder_certification_evidence" TO "authenticated";
GRANT ALL ON TABLE "public"."builder_certification_evidence" TO "service_role";



GRANT ALL ON TABLE "public"."builder_certification_policies" TO "anon";
GRANT ALL ON TABLE "public"."builder_certification_policies" TO "authenticated";
GRANT ALL ON TABLE "public"."builder_certification_policies" TO "service_role";



GRANT ALL ON TABLE "public"."builder_certification_results" TO "anon";
GRANT ALL ON TABLE "public"."builder_certification_results" TO "authenticated";
GRANT ALL ON TABLE "public"."builder_certification_results" TO "service_role";



GRANT ALL ON TABLE "public"."builder_registry" TO "anon";
GRANT ALL ON TABLE "public"."builder_registry" TO "authenticated";
GRANT ALL ON TABLE "public"."builder_registry" TO "service_role";



GRANT ALL ON TABLE "public"."capability_adapter_status" TO "service_role";



GRANT ALL ON TABLE "public"."ci_evidence_ingestions" TO "anon";
GRANT ALL ON TABLE "public"."ci_evidence_ingestions" TO "authenticated";
GRANT ALL ON TABLE "public"."ci_evidence_ingestions" TO "service_role";



GRANT ALL ON TABLE "public"."ci_repair_actions" TO "anon";
GRANT ALL ON TABLE "public"."ci_repair_actions" TO "authenticated";
GRANT ALL ON TABLE "public"."ci_repair_actions" TO "service_role";



GRANT ALL ON TABLE "public"."customer_accounts" TO "anon";
GRANT ALL ON TABLE "public"."customer_accounts" TO "authenticated";
GRANT ALL ON TABLE "public"."customer_accounts" TO "service_role";



GRANT SELECT,MAINTAIN ON TABLE "public"."deployments" TO "anon";
GRANT SELECT,MAINTAIN ON TABLE "public"."deployments" TO "authenticated";
GRANT ALL ON TABLE "public"."deployments" TO "service_role";



GRANT ALL ON TABLE "public"."environments" TO "anon";
GRANT ALL ON TABLE "public"."environments" TO "authenticated";
GRANT ALL ON TABLE "public"."environments" TO "service_role";



GRANT ALL ON TABLE "public"."factory_artifacts" TO "anon";
GRANT ALL ON TABLE "public"."factory_artifacts" TO "authenticated";
GRANT ALL ON TABLE "public"."factory_artifacts" TO "service_role";



GRANT ALL ON TABLE "public"."factory_runs" TO "anon";
GRANT ALL ON TABLE "public"."factory_runs" TO "authenticated";
GRANT ALL ON TABLE "public"."factory_runs" TO "service_role";



GRANT ALL ON TABLE "public"."generated_artifacts" TO "anon";
GRANT ALL ON TABLE "public"."generated_artifacts" TO "authenticated";
GRANT ALL ON TABLE "public"."generated_artifacts" TO "service_role";



GRANT ALL ON TABLE "public"."jobs" TO "anon";
GRANT ALL ON TABLE "public"."jobs" TO "authenticated";
GRANT ALL ON TABLE "public"."jobs" TO "service_role";



GRANT ALL ON TABLE "public"."module_registry" TO "anon";
GRANT ALL ON TABLE "public"."module_registry" TO "authenticated";
GRANT ALL ON TABLE "public"."module_registry" TO "service_role";



GRANT ALL ON TABLE "public"."organization_members" TO "anon";
GRANT ALL ON TABLE "public"."organization_members" TO "authenticated";
GRANT ALL ON TABLE "public"."organization_members" TO "service_role";



GRANT ALL ON TABLE "public"."organizations" TO "anon";
GRANT ALL ON TABLE "public"."organizations" TO "authenticated";
GRANT ALL ON TABLE "public"."organizations" TO "service_role";



GRANT ALL ON TABLE "public"."plan_catalog" TO "anon";
GRANT ALL ON TABLE "public"."plan_catalog" TO "authenticated";
GRANT ALL ON TABLE "public"."plan_catalog" TO "service_role";



GRANT ALL ON TABLE "public"."production_adapter_status" TO "service_role";



GRANT ALL ON TABLE "public"."profiles" TO "anon";
GRANT ALL ON TABLE "public"."profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."profiles" TO "service_role";



GRANT ALL ON TABLE "public"."project_members" TO "anon";
GRANT ALL ON TABLE "public"."project_members" TO "authenticated";
GRANT ALL ON TABLE "public"."project_members" TO "service_role";



GRANT ALL ON TABLE "public"."projects" TO "anon";
GRANT ALL ON TABLE "public"."projects" TO "authenticated";
GRANT ALL ON TABLE "public"."projects" TO "service_role";



GRANT ALL ON TABLE "public"."reference_saas_templates" TO "anon";
GRANT ALL ON TABLE "public"."reference_saas_templates" TO "authenticated";
GRANT ALL ON TABLE "public"."reference_saas_templates" TO "service_role";



GRANT SELECT,MAINTAIN ON TABLE "public"."release_gates" TO "anon";
GRANT SELECT,INSERT,MAINTAIN ON TABLE "public"."release_gates" TO "authenticated";
GRANT ALL ON TABLE "public"."release_gates" TO "service_role";



GRANT ALL ON TABLE "public"."repair_recipe_registry" TO "anon";
GRANT ALL ON TABLE "public"."repair_recipe_registry" TO "authenticated";
GRANT ALL ON TABLE "public"."repair_recipe_registry" TO "service_role";



GRANT ALL ON TABLE "public"."spec_compilations" TO "anon";
GRANT ALL ON TABLE "public"."spec_compilations" TO "authenticated";
GRANT ALL ON TABLE "public"."spec_compilations" TO "service_role";



GRANT ALL ON TABLE "public"."support_requests" TO "anon";
GRANT ALL ON TABLE "public"."support_requests" TO "authenticated";
GRANT ALL ON TABLE "public"."support_requests" TO "service_role";



GRANT ALL ON TABLE "public"."system_roles" TO "service_role";
GRANT SELECT ON TABLE "public"."system_roles" TO "authenticated";



GRANT ALL ON TABLE "public"."vl_cert_health" TO "service_role";
GRANT SELECT ON TABLE "public"."vl_cert_health" TO "anon";
GRANT SELECT ON TABLE "public"."vl_cert_health" TO "authenticated";



GRANT ALL ON TABLE "public"."vl_factory_status" TO "service_role";



GRANT ALL ON TABLE "public"."workflows" TO "anon";
GRANT ALL ON TABLE "public"."workflows" TO "authenticated";
GRANT ALL ON TABLE "public"."workflows" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";































