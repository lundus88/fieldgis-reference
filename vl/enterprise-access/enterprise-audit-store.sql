-- VL Enterprise Audit Store — DEVELOPMENT CONTRACT ONLY
-- Not applied automatically. No production migration/deployment authority is granted here.

create schema if not exists vl_enterprise;

create table if not exists vl_enterprise.session_visibility (
  session_fingerprint text primary key check (session_fingerprint ~ '^[0-9a-f]{64}$'),
  actor_id uuid not null,
  workspace_id uuid not null,
  project_id uuid null,
  device_id text not null,
  device_trust text not null check (device_trust in ('managed','trusted','unknown','restricted')),
  auth_method text not null,
  issued_at timestamptz not null,
  expires_at timestamptz not null,
  revoked_at timestamptz null,
  created_at timestamptz not null default now(),
  check (expires_at > issued_at)
);

create table if not exists vl_enterprise.audit_events (
  id uuid primary key default gen_random_uuid(),
  event_sha256 text not null unique check (event_sha256 ~ '^[0-9a-f]{64}$'),
  actor_id uuid not null,
  workspace_id uuid not null,
  project_id uuid null,
  action text not null,
  policy_id text not null,
  policy_version text not null,
  outcome text not null check (outcome in ('ALLOW','DENY','HOLD','ERROR')),
  reason text not null,
  session_fingerprint text not null,
  device_id text not null,
  device_trust text not null,
  auth_method text not null,
  resource_scope text not null,
  metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null,
  recorded_at timestamptz not null default now(),
  constraint audit_session_fk foreign key (session_fingerprint)
    references vl_enterprise.session_visibility(session_fingerprint)
    on update restrict on delete restrict
);

-- Metadata must be pre-redacted by the application boundary. Block common secret-bearing keys again at storage.
alter table vl_enterprise.audit_events
  add constraint audit_metadata_no_common_secret_keys check (
    not (metadata ?| array['secret','token','password','authorization','cookie','api_key','apikey','access_token','refresh_token','private_key','credential','credentials'])
  );

-- Append-only audit semantics: no UPDATE/DELETE grants should be issued to runtime roles.
-- Runtime adapters may INSERT audit events and SELECT rows already authorized by workspace/project policy.

alter table vl_enterprise.session_visibility enable row level security;
alter table vl_enterprise.audit_events enable row level security;

-- Policies intentionally depend on request-scoped settings injected by a trusted identity boundary.
-- Missing settings => no matching policy => fail closed.
create policy session_self_or_workspace_auditor_select
on vl_enterprise.session_visibility
for select
using (
  actor_id::text = nullif(current_setting('vl.actor_id', true), '')
  or (
    workspace_id::text = nullif(current_setting('vl.workspace_id', true), '')
    and current_setting('vl.workspace_auditor', true) = 'true'
  )
);

create policy audit_workspace_scoped_select
on vl_enterprise.audit_events
for select
using (
  workspace_id::text = nullif(current_setting('vl.workspace_id', true), '')
  and current_setting('vl.workspace_auditor', true) = 'true'
);

-- Insert policy is intentionally narrow and requires the trusted audit writer marker.
create policy audit_trusted_writer_insert
on vl_enterprise.audit_events
for insert
with check (
  current_setting('vl.audit_writer', true) = 'true'
  and workspace_id::text = nullif(current_setting('vl.workspace_id', true), '')
  and actor_id::text = nullif(current_setting('vl.actor_id', true), '')
);

comment on table vl_enterprise.audit_events is
'Append-only VL enterprise audit contract. Development/runtime-readiness only until separately reviewed and deployed.';
