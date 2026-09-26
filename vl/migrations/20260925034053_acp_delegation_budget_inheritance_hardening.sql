-- CANDIDATE ONLY — DO NOT APPLY DIRECTLY.
-- Human review required before conversion to an official migration.
--
-- Purpose:
--   Enforce monotonic budget inheritance for delegated ACP grants.
--   If a parent defines timeout_seconds, max_retries, or max_cost_minor,
--   every child must carry that bound explicitly and may only reduce it.
--
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
    if parent_row.budget ? key and not (new.budget ? key) then
      raise exception 'ACP delegated budget missing parent bound for %', key;
    end if;
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
