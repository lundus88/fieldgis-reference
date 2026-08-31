-- VL Agent Control Plane V1 persistence contract.
-- Repository-only migration until explicitly reviewed/applied.

create schema if not exists private;
create extension if not exists pgcrypto with schema extensions;

create table if not exists private.agent_capability_grants (
  grant_id uuid primary key default gen_random_uuid(),
  agent_id text not null,
  principal_type text not null check (principal_type in ('agent','human','system')),
  agent_version text,
  role_name text not null,
  capabilities text[] not null check (cardinality(capabilities) > 0),
  scope jsonb not null check (jsonb_typeof(scope) = 'object' and scope <> '{}'::jsonb),
  budget jsonb not null default '{"timeout_seconds":300,"max_retries":0}'::jsonb,
  delegated_from_grant_id uuid references private.agent_capability_grants(grant_id),
  valid_from timestamptz not null default now(),
  valid_until timestamptz,
  revoked_at timestamptz,
  revocation_reason text,
  created_by text not null,
  created_at timestamptz not null default now(),
  check (valid_until is null or valid_until > valid_from),
  check (revoked_at is null or revoked_at >= created_at),
  check (
    principal_type <> 'agent'
    or not (capabilities && array['production.approve','production.promote']::text[])
  )
);

create index if not exists agent_capability_grants_agent_idx
  on private.agent_capability_grants (agent_id, valid_from desc);
create index if not exists agent_capability_grants_parent_idx
  on private.agent_capability_grants (delegated_from_grant_id)
  where delegated_from_grant_id is not null;

create table if not exists private.agent_control_audit_events (
  event_id text primary key check (length(event_id) between 16 and 200),
  schema_version text not null default '1.0' check (schema_version = '1.0'),
  action_id text not null check (length(action_id) between 16 and 200),
  event_seq integer not null check (event_seq > 0),
  event_type text not null check (event_type in (
    'action_requested',
    'policy_decided',
    'execution_started',
    'execution_completed',
    'execution_failed',
    'delegation_recorded',
    'idempotent_replay'
  )),
  recorded_at timestamptz not null default now(),
  requester jsonb not null check (
    jsonb_typeof(requester) = 'object'
    and requester ? 'agent_id'
    and requester ? 'agent_version'
    and requester ? 'role'
    and requester ? 'principal_type'
  ),
  delegator_chain jsonb not null default '[]'::jsonb check (jsonb_typeof(delegator_chain) = 'array'),
  capability text not null,
  scope jsonb not null check (jsonb_typeof(scope) = 'object' and scope <> '{}'::jsonb),
  input_digest text not null check (input_digest ~ '^sha256:[a-f0-9]{64}$'),
  decision text check (decision is null or decision in ('allow','deny','require_human_approval')),
  reason_code text,
  execution_status text check (
    execution_status is null
    or execution_status in ('not_started','running','succeeded','failed','blocked')
  ),
  result_digest text check (result_digest is null or result_digest ~ '^sha256:[a-f0-9]{64}$'),
  previous_event_digest text check (previous_event_digest is null or previous_event_digest ~ '^sha256:[a-f0-9]{64}$'),
  event_digest text not null check (event_digest ~ '^sha256:[a-f0-9]{64}$'),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  unique (action_id, event_seq),
  unique (event_digest)
);

create index if not exists agent_control_audit_action_idx
  on private.agent_control_audit_events (action_id, event_seq);

create or replace function private.block_agent_audit_mutation()
returns trigger
language plpgsql
set search_path = pg_catalog, private
as $$
begin
  raise exception 'agent_control_audit_events is append-only';
end;
$$;

create or replace trigger trg_agent_control_audit_no_update
before update on private.agent_control_audit_events
for each row execute function private.block_agent_audit_mutation();

create or replace trigger trg_agent_control_audit_no_delete
before delete on private.agent_control_audit_events
for each row execute function private.block_agent_audit_mutation();

-- The grant and audit stores are private and are not direct Data API surfaces.
revoke all on table private.agent_capability_grants from public, anon, authenticated;
revoke all on table private.agent_control_audit_events from public, anon, authenticated;
revoke all on function private.block_agent_audit_mutation() from public, anon, authenticated;

comment on table private.agent_capability_grants is
  'Authoritative ACP grants. Worker agents cannot grant or widen their own authority.';
comment on table private.agent_control_audit_events is
  'Append-only ACP audit evidence aligned with audit-event.schema.json. event_digest/previous_event_digest form a tamper-evident chain.';
