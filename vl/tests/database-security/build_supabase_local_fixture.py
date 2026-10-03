#!/usr/bin/env python3
"""Build a minimal synthetic schema from the real VL migrations for local Supabase control-plane testing.
Never connects to a remote Supabase project and contains no customer/production data.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / "migrations"

def read(name: str) -> str:
    return (M / name).read_text()

def function_sql(source: str, signature: str) -> str:
    start = source.find(f"create or replace function {signature}")
    if start < 0:
        raise RuntimeError(f"missing function: {signature}")
    end = source.find("$$;", start)
    if end < 0:
        raise RuntimeError(f"missing function terminator: {signature}")
    return source[start:end + 3]

founder = read("20260901_founder_internal_usage_guardrails.sql")
execution = read("20260901_assisted_build_execution_gate.sql")
live_alignment = read("20260831_product_alignment_live_gate.sql")
alignment = read("20260901_assisted_build_product_alignment.sql")
merged_boundary = read("20260914_public_security_definer_boundary.sql")
successor = read("20260914_security_invoker_rpc_guarded_entry.sql")

project = "10000000-0000-4000-8000-000000000001"
other_project = "10000000-0000-4000-8000-000000000002"
owner = "20000000-0000-4000-8000-000000000001"
admin = "20000000-0000-4000-8000-000000000002"
member = "20000000-0000-4000-8000-000000000003"

parts = [r"""
\set ON_ERROR_STOP on
create schema if not exists private;
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

drop table if exists public.project_members cascade;
drop table if exists public.plan_catalog cascade;
drop table if exists public.projects cascade;

create table public.projects(id uuid primary key);
create table public.project_members(project_id uuid, user_id uuid, role text);
create table public.plan_catalog(plan_key text primary key, is_public boolean, limits jsonb);

alter table public.projects enable row level security;
alter table public.project_members enable row level security;
alter table public.plan_catalog enable row level security;

insert into public.projects values
  ('10000000-0000-4000-8000-000000000001'),
  ('10000000-0000-4000-8000-000000000002');
insert into public.project_members values
  ('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','owner'),
  ('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000002','admin'),
  ('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000003','member');
insert into public.plan_catalog values('launch_pilot',true,'{}'::jsonb);
"""]

marker = "create or replace function private.enforce_public_factory_quota()"
if marker not in founder:
    raise RuntimeError("founder migration marker drift")
parts.append(founder.split(marker, 1)[0] + "\ncommit;\n")

marker = "create or replace function private.enforce_assisted_build_execution_gate()"
if marker not in execution:
    raise RuntimeError("assisted build migration marker drift")
parts.append(execution.split(marker, 1)[0] + "\n")

parts.append(function_sql(live_alignment, "private.validate_product_alignment(") + "\n")
parts.append(alignment + "\n")
parts.append(merged_boundary + "\n")
parts.append(successor + "\n")
parts.append("notify pgrst, 'reload schema';\n")

sys.stdout.write("\n".join(parts))
