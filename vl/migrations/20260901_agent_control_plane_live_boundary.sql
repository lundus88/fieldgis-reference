-- VL Agent Control Plane V1 narrow live write boundary.
-- Repository-only until explicitly reviewed/applied. Depends on
-- 20260831_agent_control_plane_store.sql.
--
-- Design:
-- - service_role retains NO direct DML on private ACP tables.
-- - no runtime root-grant issuance exists.
-- - only non-production delegated agent grants may be created.
-- - revocation is limited to agent grants.
-- - audit evidence is appended atomically by the same transaction.
-- - generic/arbitrary audit-write RPC is intentionally not exposed.

create or replace function private.acp_admin_event_id(
  p_action_id text,
  p_event_type text
)
returns text
language sql
immutable
set search_path = pg_catalog, extensions
as $$
  select 'acp:' || encode(
    extensions.digest(convert_to(p_action_id || '|' || p_event_type, 'UTF8'), 'sha256'),
    'hex'
  );
$$;

create or replace function private.acp_assert_actor_evidence(p_evidence jsonb)
returns void
language plpgsql
set search_path = pg_catalog, private
as $$
begin
  if jsonb_typeof(p_evidence) <> 'object'
     or coalesce(p_evidence->>'repository', '') = ''
     or coalesce(p_evidence->>'workflow_ref', '') = ''
     or coalesce(p_evidence->>'run_id', '') = ''
     or coalesce(p_evidence->>'sha', '') = ''
     or coalesce(p_evidence->>'actor', '') = '' then
    raise exception 'ACP actor evidence incomplete';
  end if;

  if p_evidence::text ~* '(authorization|access_token|refresh_token|service_role_key|supabase_service_role_key|api_key|password|private_key|bearer_token|github_token|actions_id_token_request_token)' then
    raise exception 'ACP actor evidence contains forbidden credential field';
  end if;
end;
$$;

create or replace function private.acp_append_admin_audit_event(
  p_action_id text,
  p_event_type text,
  p_capability text,
  p_scope jsonb,
  p_input_digest text,
  p_decision text,
  p_reason_code text,
  p_execution_status text,
  p_result_digest text,
  p_metadata jsonb,
  p_actor_evidence jsonb
)
returns text
language plpgsql
set search_path = pg_catalog, private, extensions
as $$
declare
  v_event_id text;
  v_existing private.agent_control_audit_events%rowtype;
  v_prior_seq integer;
  v_prior_digest text;
  v_next_seq integer;
  v_recorded_at timestamptz := clock_timestamp();
  v_requester jsonb;
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
       and v_existing.metadata = p_metadata then
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
    'metadata', p_metadata || jsonb_build_object('actor_evidence', p_actor_evidence)
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
    v_event_digest, p_metadata || jsonb_build_object('actor_evidence', p_actor_evidence)
  );

  return v_event_digest;
end;
$$;

create or replace function public.acp_delegate_agent_grant_nonprod(
  p_action_id text,
  p_parent_grant_id uuid,
  p_agent_id text,
  p_agent_version text,
  p_role_name text,
  p_capabilities text[],
  p_scope jsonb,
  p_budget jsonb,
  p_valid_from timestamptz,
  p_valid_until timestamptz,
  p_actor_evidence jsonb
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, private, extensions
as $$
declare
  v_event_id text;
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
  if p_valid_until is null or p_valid_until <= p_valid_from then
    raise exception 'ACP bounded delegated validity required';
  end if;

  v_event_id := private.acp_admin_event_id(p_action_id, 'delegation_recorded');
  perform pg_advisory_xact_lock(hashtextextended(p_action_id, 0));

  select nullif(metadata->>'grant_id', '')::uuid into v_existing_grant_id
  from private.agent_control_audit_events
  where event_id = v_event_id;
  if found then
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

create or replace function public.acp_revoke_agent_grant(
  p_action_id text,
  p_grant_id uuid,
  p_reason text,
  p_actor_evidence jsonb
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, private, extensions
as $$
declare
  v_event_id text;
  v_scope jsonb;
  v_input_payload jsonb;
  v_input_digest text;
  v_result_digest text;
  v_existing boolean;
begin
  perform private.acp_assert_actor_evidence(p_actor_evidence);

  if p_action_id is null or length(p_action_id) < 16 or length(p_action_id) > 160 then
    raise exception 'ACP action_id invalid';
  end if;
  if p_grant_id is null or length(trim(coalesce(p_reason, ''))) < 8 then
    raise exception 'ACP revocation requires grant id and reason';
  end if;

  v_event_id := private.acp_admin_event_id(p_action_id, 'policy_decided');
  perform pg_advisory_xact_lock(hashtextextended(p_action_id, 0));

  select true into v_existing
  from private.agent_control_audit_events
  where event_id = v_event_id;
  if found then
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

  v_input_payload := jsonb_build_object('grant_id', p_grant_id, 'reason', p_reason);
  v_input_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_input_payload::text, 'UTF8'), 'sha256'), 'hex'
  );
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

-- Internal helpers are never API-callable.
revoke all on function private.acp_admin_event_id(text, text) from public, anon, authenticated, service_role;
revoke all on function private.acp_assert_actor_evidence(jsonb) from public, anon, authenticated, service_role;
revoke all on function private.acp_append_admin_audit_event(text, text, text, jsonb, text, text, text, text, text, jsonb, jsonb) from public, anon, authenticated, service_role;

-- Public RPC surface is intentionally tiny and service-role-only.
revoke all on function public.acp_delegate_agent_grant_nonprod(text, uuid, text, text, text, text[], jsonb, jsonb, timestamptz, timestamptz, jsonb) from public, anon, authenticated;
revoke all on function public.acp_revoke_agent_grant(text, uuid, text, jsonb) from public, anon, authenticated;
grant execute on function public.acp_delegate_agent_grant_nonprod(text, uuid, text, text, text, text[], jsonb, jsonb, timestamptz, timestamptz, jsonb) to service_role;
grant execute on function public.acp_revoke_agent_grant(text, uuid, text, jsonb) to service_role;

comment on function public.acp_delegate_agent_grant_nonprod(text, uuid, text, text, text, text[], jsonb, jsonb, timestamptz, timestamptz, jsonb) is
  'ACP live write boundary: delegate bounded agent grants for development/staging only; no root grant or production capability issuance.';
comment on function public.acp_revoke_agent_grant(text, uuid, text, jsonb) is
  'ACP live write boundary: revoke agent grants only; mutation is atomically audit-recorded.';
