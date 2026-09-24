-- CANDIDATE ONLY — DO NOT APPLY DIRECTLY.
-- Convert to an official Supabase migration only after human approval.
--
-- Purpose:
--   Read one authoritative ACP grant chain for a non-production LOM VPS task.
-- Security:
--   - SECURITY DEFINER is necessary because private.agent_capability_grants is
--     intentionally not selectable by service_role.
--   - Empty search_path + fully qualified objects.
--   - EXECUTE revoked from PUBLIC/anon/authenticated.
--   - No DML and no generic SQL.
--   - Exact leaf binding to agent/project/environment.
--   - Maximum 16 grant rows and explicit cycle/missing-parent rejection.

create or replace function public.acp_read_agent_grant_chain_nonprod(
  p_grant_id uuid,
  p_agent_id text,
  p_project_id text,
  p_target_environment text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
stable
as $$
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
     or v_leaf.valid_from > clock_timestamp()
     or (v_leaf.valid_until is not null and v_leaf.valid_until <= clock_timestamp()) then
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

  -- If the last returned row still points to a parent, traversal stopped because
  -- the chain exceeded the bound or an ancestor could not be read.
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

revoke all on function public.acp_read_agent_grant_chain_nonprod(uuid, text, text, text)
  from public, anon, authenticated;

grant execute on function public.acp_read_agent_grant_chain_nonprod(uuid, text, text, text)
  to service_role;

comment on function public.acp_read_agent_grant_chain_nonprod(uuid, text, text, text) is
  'Read-only non-production ACP grant-chain resolver for the dedicated server-side LOM resolver boundary. No grant mutation or direct table access is exposed.';
