-- CANDIDATE ONLY — HUMAN GATE REQUIRED — DO NOT APPLY DIRECTLY.
-- Convert to an official Supabase migration only after explicit approval.
--
-- Creates one short-lived staging parent grant for the LOM VPS path.
-- This is intentionally a migration-time human authority action, NOT a runtime RPC.

do $$
declare
  v_project_id uuid;
  v_environment_id uuid;
  v_grant_id uuid := gen_random_uuid();
  v_action_id text := 'acp-lom-vps-parent-renewal-v1-20260925';
  v_valid_from timestamptz := clock_timestamp();
  v_valid_until timestamptz;
  v_scope jsonb;
  v_budget jsonb := jsonb_build_object(
    'timeout_seconds', 60,
    'max_retries', 0,
    'max_cost_minor', 0
  );
  v_input_payload jsonb;
  v_input_digest text;
  v_result_digest text;
  v_event_id text;
  v_requester jsonb;
  v_metadata jsonb;
  v_event_payload jsonb;
  v_event_digest text;
begin
  select p.id, e.id
    into strict v_project_id, v_environment_id
  from public.projects p
  join public.environments e on e.project_id = p.id
  where p.slug = 'fieldgis-reference'
    and p.status = 'active'
    and e.kind = 'staging'
    and e.status = 'ready';

  v_valid_until := v_valid_from + interval '24 hours';
  v_scope := jsonb_build_object(
    'project_id', v_project_id::text,
    'target_environment', 'staging'
  );

  if exists (
    select 1
    from private.agent_capability_grants g
    where g.agent_id = 'lom-vps-staging-parent'
      and g.principal_type = 'system'
      and g.role_name = 'lom-vps-staging-parent'
      and g.delegated_from_grant_id is null
      and g.revoked_at is null
      and g.valid_from <= v_valid_from
      and (g.valid_until is null or g.valid_until > v_valid_from)
      and g.scope = v_scope
  ) then
    raise exception 'active LOM VPS staging parent grant already exists';
  end if;

  insert into private.agent_capability_grants (
    grant_id,
    agent_id,
    principal_type,
    agent_version,
    role_name,
    capabilities,
    scope,
    budget,
    delegated_from_grant_id,
    valid_from,
    valid_until,
    created_by
  ) values (
    v_grant_id,
    'lom-vps-staging-parent',
    'system',
    null,
    'lom-vps-staging-parent',
    array['factory.plan']::text[],
    v_scope,
    v_budget,
    null,
    v_valid_from,
    v_valid_until,
    'human-approved:lom-direct-vps-activation'
  );

  v_input_payload := jsonb_build_object(
    'project_slug', 'fieldgis-reference',
    'environment_kind', 'staging',
    'capabilities', jsonb_build_array('factory.plan'),
    'scope', v_scope,
    'budget', v_budget,
    'valid_from', v_valid_from,
    'valid_until', v_valid_until
  );

  v_input_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_input_payload::text, 'UTF8'), 'sha256'),
    'hex'
  );
  v_result_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_grant_id::text, 'UTF8'), 'sha256'),
    'hex'
  );
  v_event_id := 'acp:' || encode(
    extensions.digest(convert_to(v_action_id || '|policy_decided', 'UTF8'), 'sha256'),
    'hex'
  );

  if exists (
    select 1
    from private.agent_control_audit_events
    where action_id = v_action_id
  ) then
    raise exception 'ACP LOM VPS parent renewal action already consumed';
  end if;

  v_requester := jsonb_build_object(
    'agent_id', 'human-approval',
    'agent_version', '1',
    'role', 'founder',
    'principal_type', 'human'
  );
  v_metadata := jsonb_build_object(
    'approval_gate', 'LOM_DIRECT_VPS_PARENT',
    'approval_reference', 'APPROVE LOM VPS STAGING PARENT GRANT',
    'project_slug', 'fieldgis-reference',
    'environment_id', v_environment_id,
    'grant_id', v_grant_id,
    'bootstrap_mode', 'short-lived-staging-parent'
  );
  v_event_payload := jsonb_build_object(
    'schema_version', '1.0',
    'event_id', v_event_id,
    'action_id', v_action_id,
    'event_seq', 1,
    'event_type', 'policy_decided',
    'recorded_at', v_valid_from,
    'requester', v_requester,
    'delegator_chain', '[]'::jsonb,
    'capability', 'acp.bootstrap_parent_grant',
    'scope', v_scope,
    'input_digest', v_input_digest,
    'decision', 'allow',
    'reason_code', 'ALLOW_HUMAN_APPROVED_LOM_VPS_STAGING_PARENT',
    'execution_status', 'succeeded',
    'result_digest', v_result_digest,
    'previous_event_digest', null,
    'metadata', v_metadata
  );
  v_event_digest := 'sha256:' || encode(
    extensions.digest(convert_to(v_event_payload::text, 'UTF8'), 'sha256'),
    'hex'
  );

  insert into private.agent_control_audit_events (
    event_id, schema_version, action_id, event_seq, event_type, recorded_at,
    requester, delegator_chain, capability, scope, input_digest, decision,
    reason_code, execution_status, result_digest, previous_event_digest,
    event_digest, metadata
  ) values (
    v_event_id, '1.0', v_action_id, 1, 'policy_decided', v_valid_from,
    v_requester, '[]'::jsonb, 'acp.bootstrap_parent_grant', v_scope,
    v_input_digest, 'allow', 'ALLOW_HUMAN_APPROVED_LOM_VPS_STAGING_PARENT',
    'succeeded', v_result_digest, null, v_event_digest, v_metadata
  );
end;
$$;
