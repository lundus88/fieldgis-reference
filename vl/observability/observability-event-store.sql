-- DEVELOPMENT/CONTRACT ONLY — not deployed by this branch.
-- Append-only machine-readable observability events for blocked/non-throw decisions.

create table if not exists public.vl_observability_events (
  id bigint generated always as identity primary key,
  event_type text not null,
  factory_run_id uuid not null,
  reason_code text not null,
  source_decision_sha256 text not null check (source_decision_sha256 ~ '^[0-9a-f]{64}$'),
  event_sha256 text not null unique check (event_sha256 ~ '^[0-9a-f]{64}$'),
  payload jsonb not null,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint vl_observability_event_type_check check (event_type in (
    'release_candidate_blocked_observed',
    'historical_orphan_candidate_observed',
    'current_path_regression_observed'
  )),
  constraint vl_observability_no_secret_payload check (
    not (payload ?| array['secret','token','password','credential','authorization','cookie','api_key','access_token','refresh_token','private_key'])
  )
);

alter table public.vl_observability_events enable row level security;

-- Observability events are immutable evidence. No UPDATE/DELETE policies are defined.
-- Trusted runtime writer identity must be explicitly granted INSERT by deployment policy.
-- This contract intentionally grants no production approval or factory-run state mutation authority.

create index if not exists vl_observability_events_factory_run_idx
  on public.vl_observability_events(factory_run_id, occurred_at desc);

create index if not exists vl_observability_events_type_idx
  on public.vl_observability_events(event_type, occurred_at desc);
