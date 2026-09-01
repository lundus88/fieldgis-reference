-- Harden Billplz recovery semantics before unrestricted public billing.
-- Cancellation is terminal for unpaid orders. Refund reverses a previously fulfilled payment.
-- Duplicate events remain idempotent and late paid callbacks cannot resurrect cancelled/refunded orders.

begin;

alter table private.payment_production_orders
  drop constraint if exists payment_production_orders_status_check;
alter table private.payment_production_orders
  add constraint payment_production_orders_status_check
  check (status = any (array['pending'::text,'paid'::text,'cancelled'::text,'failed'::text,'refunded'::text]));

alter table private.payment_production_orders
  drop constraint if exists payment_production_orders_fulfillment_state_check;
alter table private.payment_production_orders
  add constraint payment_production_orders_fulfillment_state_check
  check (fulfillment_state = any (array['unfulfilled'::text,'fulfilled'::text,'blocked'::text,'reversed'::text]));

create or replace function private.apply_billplz_sandbox_webhook(
  p_event_key text,
  p_provider_bill_id text,
  p_payload_sha256 text,
  p_normalized_status text,
  p_amount_minor integer
)
returns jsonb
language plpgsql
security definer
set search_path = private, pg_temp
as $$
declare
  v_order private.payment_sandbox_orders%rowtype;
  v_existing private.payment_webhook_events%rowtype;
  v_applied boolean := false;
  v_now timestamptz := now();
  v_reason text := 'no_state_change';
begin
  if coalesce(trim(p_event_key),'') = '' or coalesce(trim(p_provider_bill_id),'') = '' then
    raise exception 'invalid webhook identity';
  end if;
  if p_normalized_status not in ('paid','pending','cancelled','refunded') then
    raise exception 'invalid normalized status';
  end if;

  select * into v_existing from private.payment_webhook_events where event_key = p_event_key;
  if found then
    return jsonb_build_object('ok',true,'duplicate',true,'applied',false,'status',v_existing.normalized_status,'reason','duplicate_event');
  end if;

  select * into v_order from private.payment_sandbox_orders
   where provider_bill_id = p_provider_bill_id
   for update;
  if not found then raise exception 'unknown sandbox bill'; end if;
  if v_order.environment <> 'sandbox' or v_order.adapter_key <> 'billplz-payment-v1' then
    raise exception 'sandbox adapter invariant failed';
  end if;
  if p_amount_minor is distinct from v_order.amount_minor then raise exception 'amount mismatch'; end if;
  if v_order.currency <> 'MYR' then raise exception 'currency mismatch'; end if;

  if p_normalized_status = 'paid' then
    if v_order.status = 'pending' and v_order.fulfillment_state = 'unfulfilled' then
      update private.payment_sandbox_orders
         set status='paid', paid_at=coalesce(paid_at,v_now), updated_at=v_now,
             metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
               'payment_confirmed_by','billplz_signed_webhook',
               'fulfillment_separated',true
             )
       where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
      v_applied := found;
      v_reason := case when v_applied then 'pending_to_paid' else 'race_blocked' end;
    elsif v_order.status in ('cancelled','refunded') then
      v_reason := 'terminal_order_not_resurrected';
    else
      v_reason := 'paid_state_unchanged';
    end if;
  elsif p_normalized_status = 'cancelled' then
    update private.payment_sandbox_orders
       set status='cancelled',updated_at=v_now
     where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'pending_to_cancelled' else 'cancellation_not_applicable' end;
  elsif p_normalized_status = 'refunded' then
    update private.payment_sandbox_orders
       set status='refunded',fulfillment_state='reversed',updated_at=v_now,
           metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object('refund_confirmed_by','billplz_signed_webhook')
     where id=v_order.id and status='paid' and fulfillment_state='fulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'paid_to_refunded_reversed' else 'refund_not_applicable' end;
  end if;

  begin
    insert into private.payment_webhook_events(
      adapter_key,event_key,provider_bill_id,payload_sha256,signature_valid,
      normalized_status,amount_minor,applied,duplicate,processed_at,metadata
    ) values (
      'billplz-payment-v1',p_event_key,p_provider_bill_id,p_payload_sha256,true,
      p_normalized_status,p_amount_minor,v_applied,false,v_now,
      jsonb_build_object('environment','sandbox','authoritative_source','server_callback','fulfillment_mutated',p_normalized_status='refunded' and v_applied,'reason',v_reason)
    );
  exception when unique_violation then
    return jsonb_build_object('ok',true,'duplicate',true,'applied',false,'status',p_normalized_status,'reason','duplicate_event');
  end;

  return jsonb_build_object('ok',true,'duplicate',false,'applied',v_applied,'status',p_normalized_status,'reason',v_reason,'fulfillment_mutated',p_normalized_status='refunded' and v_applied);
end;
$$;

create or replace function public.vl_apply_billplz_production_test_webhook(
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
  v_event private.payment_production_webhook_events%rowtype;
  v_applied boolean := false;
  v_reason text := 'no_state_change';
begin
  if current_user not in ('service_role','postgres') then raise exception 'service role required'; end if;
  if p_normalized_status not in ('paid','pending','cancelled','refunded') then raise exception 'invalid normalized status'; end if;

  select * into v_order from private.payment_production_orders where provider_bill_id=p_provider_bill_id for update;
  if not found then raise exception 'unknown production test bill'; end if;
  if v_order.purpose<>'controlled_live_test' or v_order.amount_minor<>100 or v_order.currency<>'MYR' then raise exception 'production test invariant failed'; end if;
  if p_amount_minor<>v_order.amount_minor then raise exception 'amount mismatch'; end if;

  select * into v_event from private.payment_production_webhook_events where event_key=p_event_key;
  if found then
    return jsonb_build_object('ok',true,'duplicate',true,'applied',false,'status',v_order.status,'order_id',v_order.id,'reason','duplicate_event');
  end if;

  if p_normalized_status='paid' then
    if v_order.status='pending' and v_order.fulfillment_state='unfulfilled' then
      update private.payment_production_orders
         set status='paid',paid_at=coalesce(paid_at,now()),fulfillment_state='fulfilled',updated_at=now()
       where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
      v_applied := found;
      if v_applied then
        insert into private.payment_production_fulfillment_events(order_id,action_key,status,evidence)
        values(v_order.id,'billplz-production-test:'||v_order.id::text,'fulfilled',jsonb_build_object('payment_status','paid','amount_minor',100,'currency','MYR','provider_bill_id',p_provider_bill_id,'exactly_once',true))
        on conflict(action_key) do nothing;
      end if;
      v_reason := case when v_applied then 'pending_to_paid_fulfilled' else 'race_blocked' end;
    elsif v_order.status in ('cancelled','refunded') then
      v_reason := 'terminal_order_not_resurrected';
    else
      v_reason := 'paid_state_unchanged';
    end if;
  elsif p_normalized_status='cancelled' then
    update private.payment_production_orders set status='cancelled',updated_at=now()
     where id=v_order.id and status='pending' and fulfillment_state='unfulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'pending_to_cancelled' else 'cancellation_not_applicable' end;
  elsif p_normalized_status='refunded' then
    update private.payment_production_orders
       set status='refunded',fulfillment_state='reversed',updated_at=now()
     where id=v_order.id and status='paid' and fulfillment_state='fulfilled';
    v_applied := found;
    v_reason := case when v_applied then 'paid_to_refunded_reversed' else 'refund_not_applicable' end;
  end if;

  insert into private.payment_production_webhook_events(event_key,provider_bill_id,payload_sha256,signature_valid,normalized_status,amount_minor,applied,duplicate,processed_at,metadata)
  values(p_event_key,p_provider_bill_id,p_payload_sha256,true,p_normalized_status,p_amount_minor,v_applied,false,now(),jsonb_build_object('environment','production','purpose','controlled_live_test','reason',v_reason));

  return jsonb_build_object('ok',true,'duplicate',false,'applied',v_applied,'status',p_normalized_status,'order_id',v_order.id,'reason',v_reason);
end;
$$;

commit;
