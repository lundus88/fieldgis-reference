-- LOM Economic Participation P0
-- DEVELOPMENT / NON-PRODUCTION SCHEMA SPECIFICATION ONLY.
-- This file is not a Production migration and grants no payout authority.

create table if not exists lom_ep_funding_allocations (
  funding_id text primary key,
  approved_minor bigint not null check (approved_minor >= 0),
  reserved_minor bigint not null check (reserved_minor >= 0 and reserved_minor <= approved_minor),
  spent_minor bigint not null default 0 check (spent_minor >= 0 and spent_minor <= approved_minor),
  currency text not null default 'MYR',
  status text not null default 'APPROVED',
  created_at timestamptz not null default now()
);

create table if not exists lom_ep_worker_profiles (
  worker_id uuid primary key,
  stage text not null check (stage in ('STARTER','VERIFIED','SPECIALIST','SENIOR')),
  active boolean not null default true,
  integrity_clear boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists lom_ep_tasks (
  task_id uuid primary key,
  task_type text not null check (task_type = 'SCRIPT_POLISH'),
  funding_id text not null references lom_ep_funding_allocations(funding_id),
  worker_id uuid references lom_ep_worker_profiles(worker_id),
  worker_fee_minor bigint not null check (worker_fee_minor > 0),
  status text not null,
  revision_count smallint not null default 0 check (revision_count between 0 and 2),
  qa_result_id uuid,
  security_hold boolean not null default false,
  dispute_open boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists lom_ep_submissions (
  submission_id uuid primary key,
  task_id uuid not null references lom_ep_tasks(task_id),
  worker_id uuid not null references lom_ep_worker_profiles(worker_id),
  version_no integer not null check (version_no > 0),
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique(task_id, version_no)
);

create table if not exists lom_ep_qa_results (
  qa_result_id uuid primary key,
  task_id uuid not null references lom_ep_tasks(task_id),
  score integer not null check (score between 0 and 100),
  confidence numeric not null check (confidence between 0 and 1),
  decision text not null check (decision in ('PASS','REVISION','ESCALATE','REJECT')),
  reason_codes text[] not null default '{}',
  policy_version text not null,
  created_at timestamptz not null default now()
);

create table if not exists lom_ep_earnings_entitlements (
  entitlement_id uuid primary key,
  task_id uuid not null unique references lom_ep_tasks(task_id),
  worker_id uuid not null references lom_ep_worker_profiles(worker_id),
  funding_id text not null references lom_ep_funding_allocations(funding_id),
  amount_minor bigint not null check (amount_minor > 0),
  currency text not null,
  status text not null check (status in (
    'ELIGIBLE_FOR_HUMAN_PAYOUT_REVIEW','HELD','PROCESSING','PAID','RECONCILED','DISPUTED'
  )),
  payment_provider_reference text,
  created_at timestamptz not null default now()
);

create table if not exists lom_ep_reputation_evidence_events (
  event_id uuid primary key,
  worker_id uuid not null references lom_ep_worker_profiles(worker_id),
  task_id uuid references lom_ep_tasks(task_id),
  dimension text not null,
  signal text not null,
  reason_code text not null,
  evidence_ref text not null,
  source_event_id text not null,
  authoritative_aggregate boolean not null default false check (authoritative_aggregate = false),
  created_at timestamptz not null default now()
);

create table if not exists lom_ep_audit_events (
  audit_id uuid primary key,
  task_id uuid not null references lom_ep_tasks(task_id),
  actor text not null,
  event text not null,
  previous_status text not null,
  next_status text not null,
  result text not null,
  reason text not null,
  event_digest text not null,
  created_at timestamptz not null default now()
);

-- Recommended RLS intent:
-- worker: SELECT own assignments/submissions/earnings; INSERT own submissions only.
-- QA service: QA records only; cannot write payout state.
-- finance adapter: earnings/payment fields only after state-machine guard.
-- direct UPDATE of lom_ep_tasks.status by client roles: DENY.
