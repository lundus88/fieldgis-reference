-- Prevent post-creation rebinding of a release or approval to a different
-- project, workflow, or factory run. Content/certificate lifecycle fields are
-- intentionally left to the existing state-machine guards.

create or replace function private.enforce_release_identity_binding()
returns trigger
language plpgsql
security invoker
set search_path = public, private, pg_temp
as $$
begin
  if new.project_id is distinct from old.project_id
     or new.workflow_id is distinct from old.workflow_id
     or new.factory_run_id is distinct from old.factory_run_id then
    raise exception 'immutable release identity binding: project/workflow/factory run cannot change';
  end if;
  return new;
end;
$$;

revoke all on function private.enforce_release_identity_binding() from public;
revoke all on function private.enforce_release_identity_binding() from anon;
revoke all on function private.enforce_release_identity_binding() from authenticated;

drop trigger if exists trg_enforce_deployment_identity_binding on public.deployments;
create trigger trg_enforce_deployment_identity_binding
before update on public.deployments
for each row execute function private.enforce_release_identity_binding();

drop trigger if exists trg_enforce_approval_identity_binding on public.approvals;
create trigger trg_enforce_approval_identity_binding
before update on public.approvals
for each row execute function private.enforce_release_identity_binding();

