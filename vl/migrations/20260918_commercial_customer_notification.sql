-- LUNDUS DIGITAL SYSTEMS / VL
-- Commercial customer notification production RC.
-- REVIEW ONLY. Do not apply to Production without explicit human approval.

begin;

alter table private.notification_outbox
  drop constraint if exists notification_outbox_environment_check;
alter table private.notification_outbox
  add constraint notification_outbox_environment_check
  check (environment = any (array[
    'sandbox'::text,'development'::text,'staging'::text,'production'::text
  ]));

create or replace function public.vl_record_commercial_notification_send(
  p_order_id uuid,
  p_template_key text,
  p_recipient_hash text,
  p_subject text,
  p_provider_message_id text,
  p_idempotency_key text,
  p_created_by uuid
)
returns jsonb
language plpgsql
security definer
set search_path=private,public,pg_temp
as $$
declare
  v_order private.payment_production_orders%rowtype;
  v private.notification_outbox%rowtype;
begin
  if current_user not in ('service_role','postgres') then raise exception 'service role required'; end if;
  if coalesce(trim(p_recipient_hash),'')=''
     or coalesce(trim(p_provider_message_id),'')=''
     or coalesce(trim(p_idempotency_key),'')='' then
    raise exception 'required notification evidence missing';
  end if;
  if p_template_key not in ('payment_confirmed','order_fulfilled','order_closed') then
    raise exception 'invalid commercial notification template';
  end if;

  select * into v_order from private.payment_production_orders where id=p_order_id;
  if not found then raise exception 'commercial order not found'; end if;
  if v_order.environment<>'production' or v_order.purpose<>'commercial_order' then
    raise exception 'production commercial order required';
  end if;

  if p_template_key='payment_confirmed' and v_order.status<>'paid' then
    raise exception 'paid order required for payment confirmation';
  end if;
  if p_template_key='order_fulfilled' and v_order.fulfillment_state<>'fulfilled' then
    raise exception 'fulfilled order required';
  end if;
  if p_template_key='order_closed'
     and coalesce((v_order.metadata->>'commercial_closed')::boolean,false)<>true then
    raise exception 'closed order evidence required';
  end if;

  select * into v from private.notification_outbox
  where adapter_key='resend-email-v1'
    and environment='production'
    and idempotency_key=p_idempotency_key
  for update;

  if found then
    if v.provider_message_id is distinct from p_provider_message_id then
      raise exception 'notification idempotency conflict';
    end if;
    return jsonb_build_object(
      'ok',true,'duplicate',true,'id',v.id,
      'provider_message_id',v.provider_message_id,'status',v.status
    );
  end if;

  insert into private.notification_outbox(
    adapter_key,channel,recipient_hash,template_key,subject,
    provider_message_id,idempotency_key,environment,status,metadata
  ) values (
    'resend-email-v1','email',p_recipient_hash,p_template_key,left(p_subject,200),
    p_provider_message_id,p_idempotency_key,'production','sent',
    jsonb_build_object(
      'order_id',p_order_id,
      'created_by',p_created_by,
      'provider','resend',
      'pii_stored',false,
      'production_send',true,
      'commercial_customer_notification',true
    )
  ) returning * into v;

  return jsonb_build_object(
    'ok',true,'duplicate',false,'id',v.id,
    'provider_message_id',v.provider_message_id,'status',v.status
  );
exception when unique_violation then
  select * into v from private.notification_outbox
  where adapter_key='resend-email-v1'
    and environment='production'
    and idempotency_key=p_idempotency_key;
  if v.provider_message_id is distinct from p_provider_message_id then
    raise exception 'notification idempotency conflict';
  end if;
  return jsonb_build_object(
    'ok',true,'duplicate',true,'id',v.id,
    'provider_message_id',v.provider_message_id,'status',v.status
  );
end;
$$;

revoke all on function public.vl_record_commercial_notification_send(uuid,text,text,text,text,text,uuid)
  from public,anon,authenticated;
grant execute on function public.vl_record_commercial_notification_send(uuid,text,text,text,text,text,uuid)
  to service_role;

create or replace function private.apply_resend_production_webhook(
  p_event_key text,
  p_provider_message_id text,
  p_event_type text,
  p_status text,
  p_payload_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path=private,pg_temp
as $$
declare
  v_existing private.notification_events%rowtype;
  v_current text;
  v_next text;
  v_rows int:=0;
  v_matched boolean:=false;
  v_applied boolean:=false;
begin
  if current_user not in ('service_role','postgres') then raise exception 'service role required'; end if;
  if coalesce(trim(p_event_key),'')='' then raise exception 'event_key required'; end if;

  select * into v_existing from private.notification_events where event_key=p_event_key;
  if found then
    return jsonb_build_object('duplicate',true,'applied',false,'event_type',p_event_type);
  end if;

  if coalesce(p_provider_message_id,'')<>'' and p_status is not null then
    select status into v_current
    from private.notification_outbox
    where provider_message_id=p_provider_message_id
      and adapter_key='resend-email-v1'
      and environment='production'
    for update;

    if found then
      v_matched:=true;
      v_next:=case
        when v_current in ('bounced','failed') then v_current
        when p_status in ('bounced','failed') then p_status
        when v_current='delivered' then 'delivered'
        when p_status='delivered' then 'delivered'
        when v_current='sent' then 'sent'
        when p_status='sent' then 'sent'
        else coalesce(p_status,v_current)
      end;

      if v_next is distinct from v_current then
        update private.notification_outbox
        set status=v_next,updated_at=now()
        where provider_message_id=p_provider_message_id
          and adapter_key='resend-email-v1'
          and environment='production';
        get diagnostics v_rows=row_count;
        v_applied:=v_rows>0;
      end if;
    end if;
  end if;

  begin
    insert into private.notification_events(
      adapter_key,provider_message_id,event_key,event_type,signature_valid,
      payload_sha256,duplicate,applied,processed_at,metadata
    ) values (
      'resend-email-v1',nullif(p_provider_message_id,''),p_event_key,
      coalesce(nullif(p_event_type,''),'unknown'),true,p_payload_sha256,
      false,v_applied,now(),
      jsonb_build_object(
        'environment','production',
        'pii_stored',false,
        'matched_outbox',v_matched,
        'previous_status',v_current,
        'resulting_status',coalesce(v_next,v_current)
      )
    );
  exception when unique_violation then
    return jsonb_build_object('duplicate',true,'applied',false,'event_type',p_event_type);
  end;

  return jsonb_build_object(
    'duplicate',false,'applied',v_applied,
    'event_type',p_event_type,'status',coalesce(v_next,v_current)
  );
end;
$$;

revoke all on function private.apply_resend_production_webhook(text,text,text,text,text)
  from public,anon,authenticated;
grant execute on function private.apply_resend_production_webhook(text,text,text,text,text)
  to service_role;

create or replace function public.vl_apply_resend_production_webhook(
  p_event_key text,
  p_provider_message_id text,
  p_event_type text,
  p_status text,
  p_payload_sha256 text
)
returns jsonb
language sql
security definer
set search_path=private,public,pg_temp
as $$
  select private.apply_resend_production_webhook(
    p_event_key,p_provider_message_id,p_event_type,p_status,p_payload_sha256
  )
$$;

revoke all on function public.vl_apply_resend_production_webhook(text,text,text,text,text)
  from public,anon,authenticated;
grant execute on function public.vl_apply_resend_production_webhook(text,text,text,text,text)
  to service_role;

commit;
