-- VL Agent Control Plane V1 persistence contract.
-- Repository-only migration until explicitly reviewed/applied.

create schema if not exists private;
create extension if not exists pgcrypto with schema extensions;

create table if not exists private.agent_capability_grants (
  grant_id uuid primary key default gen_random_uuid(),
  principal_id text not null,
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

create index if not exists agent_capability_grants_principal_idx
  on private.agent_capability_grants (principal_id, valid_from desc);
create index if not exists agent_capability_grants_parent_idx
  on private.agent_capability_grants (delegated_from_grant_id)
  where delegated_from_grant_id is not null;

create table if not exists private.agent_control_audit_events (
  event_id uuid primary key default gen_random_uuid(),
  action_id text not null,
  event_seq integer not null check (event_seq > 0),
  event_type text not null check (event_type in ('request','decision','execution','delegation','idempotent_replay')),
  actor_id text not null,
  delegator_id text,
  capability text not null,
  resource_scope jsonb not null check (jsonb_typeof(resource_scope) = 'object'),
  input_digest text not null check (input_digest ~ '^sha256:[a-f0-9]{64}$'),
  decision text check (decision is null or decision in ('allow','deny','require_human_approval')),
  reason_code text,
  execution_status text,
  evidence jsonb not null default '{}'::jsonb,
  previous_event_hash text check (previous_event_hash is null or previous_event_hash ~ '^sha256:[a-f0-9]{64}$'),
  event_hash text not null check (event_hash ~ '^sha256:[a-f0-9]{64}$'),
  occurred_at timestamptz not null default now(),
  unique (action_id, event_seq),
  unique (event_hash)
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

-- The audit store is private and is not a direct Data API surface.
revoke all on table private.agent_capability_grants from public, anon, authenticated;
revoke all on table private.agent_control_audit_events from public, anon, authenticated;
revoke all on function private.block_agent_audit_mutation() from public, anon, authenticated;

comment on table private.agent_capability_grants is
  'Authoritative ACP grants. Worker agents cannot grant or widen their own authority.';
comment on table private.agent_control_audit_events is
  'Append-only ACP audit evidence. event_hash/previous_event_hash form a tamper-evident chain.';
