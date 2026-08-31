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
  budget jsonb not null default '{"timeout_seconds":300,"max_retries":0}'::jsonb check (jsonb_typeof(budget) = 'object'),
  delegated_from_grant_id uuid references private.agent_capability_grants(grant_id),
  valid_from timestamptz not null default now(),
  valid_until timestamptz,
  revoked_at timestamptz,
  revocation_reason text,
  created_by text not null,
  created_at timestamptz not null default now(),
  check (valid_until is null or valid_until > valid_from),
  check (revoked_at is null or revoked_at >= created_at),
  check (principal_type <> 'agent' or agent_version is not null),
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

create or replace function private.validate_agent_capability_grant()
returns trigger
language plpgsql
set search_path = pg_catalog, private
as $$
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

create or replace trigger trg_agent_capability_grant_validate
before insert or update on private.agent_capability_grants
for each row execute function private.validate_agent_capability_grant();

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

create or replace function private.validate_agent_audit_chain()
returns trigger
language plpgsql
set search_path = pg_catalog, private
as $$
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

create or replace trigger trg_agent_control_audit_chain
before insert on private.agent_control_audit_events
for each row execute function private.validate_agent_audit_chain();

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

create or replace trigger trg_agent_control_audit_no_truncate
before truncate on private.agent_control_audit_events
for each statement execute function private.block_agent_audit_mutation();

-- Private stores are closed by default. A future narrowly scoped control-plane
-- function may receive explicit rights; worker/service roles do not get direct DML.
revoke all on table private.agent_capability_grants from public, anon, authenticated, service_role;
revoke all on table private.agent_control_audit_events from public, anon, authenticated, service_role;
revoke all on function private.validate_agent_capability_grant() from public, anon, authenticated, service_role;
revoke all on function private.validate_agent_audit_chain() from public, anon, authenticated, service_role;
revoke all on function private.block_agent_audit_mutation() from public, anon, authenticated, service_role;

comment on table private.agent_capability_grants is
  'Authoritative ACP grants with DB-level monotonic delegation validation. Worker agents cannot grant or widen their own authority.';
comment on table private.agent_control_audit_events is
  'Append-only ACP audit evidence aligned with audit-event.schema.json. Sequence and previous digest are DB-validated.';
