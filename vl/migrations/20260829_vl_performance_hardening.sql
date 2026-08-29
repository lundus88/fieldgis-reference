-- VL performance hardening
-- Safe intent: preserve authorization semantics while reducing per-row auth.uid() evaluation
-- and add covering indexes for foreign keys flagged by Supabase advisors.

begin;

-- Covering indexes for foreign keys.
create index if not exists customer_accounts_plan_key_idx
  on public.customer_accounts(plan_key);

create index if not exists support_requests_customer_account_id_idx
  on public.support_requests(customer_account_id);

create index if not exists support_requests_opened_by_idx
  on public.support_requests(opened_by);

-- Preserve existing RLS semantics, but use scalar subselects so auth.uid() is initialized once.
alter policy customer_accounts_insert_own
  on public.customer_accounts
  with check (owner_user_id = (select auth.uid()));

alter policy customer_accounts_select_own
  on public.customer_accounts
  using (owner_user_id = (select auth.uid()));

alter policy customer_accounts_update_own
  on public.customer_accounts
  using (owner_user_id = (select auth.uid()))
  with check (owner_user_id = (select auth.uid()));

alter policy support_requests_insert_own
  on public.support_requests
  with check (
    opened_by = (select auth.uid())
    and exists (
      select 1
      from public.customer_accounts ca
      where ca.id = support_requests.customer_account_id
        and ca.owner_user_id = (select auth.uid())
    )
  );

alter policy support_requests_select_own
  on public.support_requests
  using (opened_by = (select auth.uid()));

commit;
