-- LUNDUS DIGITAL SYSTEMS / VL
-- P0 commercial payment production readiness RC.
-- REVIEW ONLY: do not apply to Production without explicit human approval.

begin;

create table if not exists private.commercial_offers (
  offer_key text primary key,
  offer_type text not null default 'customer_quote'
    check (offer_type in ('customer_quote','public_fixed')),
  customer_account_id uuid references public.customer_accounts(id),
  display_name text not null,
  amount_minor integer not null check (amount_minor > 0),
  currency text not null default 'MYR' check (currency = 'MYR'),
  status text not null default 'draft' check (status in ('draft','active','retired')),
  fulfillment_mode text not null default 'manual'
    check (fulfillment_mode in ('manual','product_adapter')),
  valid_until timestamptz,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (offer_type='customer_quote' and customer_account_id is not null and valid_until is not null)
    or
    (offer_type='public_fixed' and customer_account_id is null)
  )
);

alter table private.commercial_offers enable row level security;
revoke all on private.commercial_offers from public, anon, authenticated;
grant select, insert, update, delete on private.commercial_offers to service_role;

create index if not exists commercial_offers_status_idx
  on private.commercial_offers(status);
create index if not exists commercial_offers_customer_status_idx
  on private.commercial_offers(customer_account_id,status);
create index if not exists commercial_offers_valid_until_idx
  on private.commercial_offers(valid_until);

alter table private.payment_production_orders
  add column if not exists offer_key text references private.commercial_offers(offer_key);
alter table private.payment_production_orders
  add column if not exists customer_account_id uuid references public.customer_accounts(id);

create index if not exists payment_production_orders_offer_idx
  on private.payment_production_orders(offer_key);
create index if not exists payment_production_orders_customer_idx
  on private.payment_production_orders(customer_account_id);

create unique index if not exists payment_production_orders_active_customer_offer_uq
  on private.payment_production_orders(customer_account_id,offer_key)
  where purpose='commercial_order'
    and offer_key is not null
    and customer_account_id is not null
    and status in ('pending','paid');

create or replace function public.vl_apply_billplz_production_webhook(
  p_event_key text,
  p_provider_bill_id text,
  p_payload_sha256 text,
  p_normalized_status text,
  p_amount_minor integer
)
returns jsonb
language plpgsql
security definer
set search_path = private, public, pg_temp
as $$
declare
  v_order private.payment_production_orders%rowtype;
  v_existing private.payment_production_webhook_events%rowtype;
  v_applied boolean := false;
  v_reason text := 'no_state_change';
  v_now timestamptz := now();
  v_next_fulfillment text;
begin
  if current_user not in ('service_role','postgres') then
    raise exception 'service role required';
  end if;
  if coalesce(trim(p_event_key),'')='' or coalesce(trim(p_provider_bill_id),'')='' then
    raise exception 'invalid webhook identity';
  end if;
  if p_normalized_status not in ('paid','pending','cancelled','refunded') then
    raise exception 'invalid normalized status';
  end if;

  select * into v_existing
    from private.payment_production_webhook_events
   where event_key=p_event_key;
  if found then
    return jsonb_build_object(
      'ok',true,'duplicate',true,'applied',false,
      'status',v_existing.normalized_status,'reason','duplicate_event'
    );
  end if;

  select * into v_order
    from private.payment_production_orders
   where provider_bill_id=p_provider_bill_id
   for update;
  if not found then raise exception 'unknown production bill'; end if;

  if v_order.environment<>'production'
     or v_order.adapter_key<>'billplz-payment-v1'
     or v_order.purpose<>'commercial_order'
     or v_order.offer_key is null
     or v_order.customer_account_id is null then
    raise exception 'production commercial order invariant failed';
  end if;
  if p_amount_minor is distinct from v_order.amount_minor then raise exception 'amount mismatch'; end if;
  if v_order.currency<>'MYR' then raise exception 'currency mismatch'; end if;

  if p_normalized_status='paid' then
    if v_order.status='pending' and v_order.fulfillment_state='unfulfilled' then
      update private.payment_production_orders
         set status='paid',
             paid_at=coalesce(paid_at,v_now),
             updated_at=v_now,
             metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
               'payment_confirmed_by','billplz_signed_webhook',
               'fulfillment_separated',true
             )
       where id=v_order.id
         and status='pending'
         and fulfillment_state='unfulfilled';
      v_applied := found;
      v_reason := case when v_applied then 'pending_to_paid_awaiting_fulfillment' else 'race_blocked' end;
    elsif v_order.status in ('cancelled','refunded') then
      v_reason := 'terminal_order_not_resurrected';
    else
      v_reason := 'paid_state_unchanged';
    end if;
  elsif p_normalized_status='cancelled' then
    update private.payment_production_orders
       set status='cancelled',updated_at=v_now
     where id=v_order.id
       and status='pending'
       and fulfillment_state='unfulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'pending_to_cancelled' else 'cancellation_not_applicable' end;
  elsif p_normalized_status='refunded' then
    v_next_fulfillment := case
      when v_order.fulfillment_state='fulfilled' then 'reversed'
      else v_order.fulfillment_state
    end;
    update private.payment_production_orders
       set status='refunded',
           fulfillment_state=v_next_fulfillment,
           updated_at=v_now,
           metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
             'refund_confirmed_by','billplz_signed_webhook'
           )
     where id=v_order.id
       and status='paid';
    v_applied := found;
    v_reason := case when v_applied then 'paid_to_refunded' else 'refund_not_applicable' end;
  end if;

  begin
    insert into private.payment_production_webhook_events(
      event_key,provider_bill_id,payload_sha256,signature_valid,
      normalized_status,amount_minor,applied,duplicate,processed_at,metadata
    ) values (
      p_event_key,p_provider_bill_id,p_payload_sha256,true,
      p_normalized_status,p_amount_minor,v_applied,false,v_now,
      jsonb_build_object(
        'environment','production',
        'purpose','commercial_order',
        'authoritative_source','billplz_signed_webhook',
        'offer_key',v_order.offer_key,
        'customer_account_id',v_order.customer_account_id,
        'fulfillment_separated',true,
        'reason',v_reason
      )
    );
  exception when unique_violation then
    return jsonb_build_object(
      'ok',true,'duplicate',true,'applied',false,
      'status',p_normalized_status,'reason','duplicate_event'
    );
  end;

  return jsonb_build_object(
    'ok',true,
    'duplicate',false,
    'applied',v_applied,
    'status',p_normalized_status,
    'order_id',v_order.id,
    'reason',v_reason,
    'fulfillment_state',case
      when p_normalized_status='paid' and v_applied then 'unfulfilled'
      else v_order.fulfillment_state
    end
  );
end;
$$;

revoke all on function public.vl_apply_billplz_production_webhook(text,text,text,text,integer)
  from public, anon, authenticated;
grant execute on function public.vl_apply_billplz_production_webhook(text,text,text,text,integer)
  to service_role;

comment on function public.vl_apply_billplz_production_webhook(text,text,text,text,integer)
is 'Production Billplz commercial payment confirmation. Service-role only; payment confirmation never auto-fulfils.';

commit;
