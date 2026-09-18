-- LUNDUS DIGITAL SYSTEMS / VL
-- Commercial fulfilment + receipt/invoice + close RC.
-- REVIEW ONLY. Do not apply to Production without explicit human approval.

begin;

create table if not exists private.commercial_order_documents (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references private.payment_production_orders(id) on delete restrict,
  document_type text not null check (document_type in ('receipt','invoice')),
  reference text not null unique,
  amount_minor integer not null check (amount_minor > 0),
  currency text not null default 'MYR' check (currency='MYR'),
  status text not null default 'issued' check (status in ('issued','void')),
  issued_by uuid not null references auth.users(id),
  issued_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

alter table private.commercial_order_documents enable row level security;
revoke all on private.commercial_order_documents from public, anon, authenticated;
grant select,insert,update on private.commercial_order_documents to service_role;

create index if not exists commercial_order_documents_order_idx
  on private.commercial_order_documents(order_id,document_type,status);

create unique index if not exists commercial_order_documents_active_type_uq
  on private.commercial_order_documents(order_id,document_type)
  where status='issued';

create table if not exists private.commercial_order_closures (
  order_id uuid primary key references private.payment_production_orders(id) on delete restrict,
  closed_by uuid not null references auth.users(id),
  closed_at timestamptz not null default now(),
  rationale text,
  evidence jsonb not null default '{}'::jsonb
);

alter table private.commercial_order_closures enable row level security;
revoke all on private.commercial_order_closures from public, anon, authenticated;
grant select,insert on private.commercial_order_closures to service_role;

create or replace function public.vl_fulfill_commercial_order(
  p_order_id uuid,
  p_action_key text,
  p_receipt_reference text,
  p_invoice_reference text default null,
  p_delivery_evidence jsonb default '{}'::jsonb,
  p_rationale text default null
)
returns jsonb
language plpgsql
security definer
set search_path=private,public,extensions,pg_temp
as $$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  v_is_operator boolean:=false;
  v_order private.payment_production_orders%rowtype;
  v_prior private.payment_production_fulfillment_events%rowtype;
  v_signed_paid boolean:=false;
  v_receipt text:=upper(trim(coalesce(p_receipt_reference,'')));
  v_invoice text:=upper(trim(coalesce(p_invoice_reference,'')));
begin
  if v_uid is null then raise exception 'authenticated operator required'; end if;
  if v_aal<>'aal2' then raise exception 'AAL2 MFA required for commercial fulfilment'; end if;

  select exists(
    select 1 from public.project_members pm
    where pm.user_id=v_uid and pm.role in ('owner','admin')
  ) into v_is_operator;
  if not v_is_operator then raise exception 'owner/admin fulfilment approval required'; end if;

  if coalesce(trim(p_action_key),'')='' or length(trim(p_action_key))<8 then
    raise exception 'invalid action key';
  end if;
  if v_receipt='' or length(v_receipt)>80 then raise exception 'valid receipt reference required'; end if;
  if v_invoice<>'' and length(v_invoice)>80 then raise exception 'invalid invoice reference'; end if;
  if jsonb_typeof(coalesce(p_delivery_evidence,'{}'::jsonb))<>'object' then
    raise exception 'delivery evidence must be a JSON object';
  end if;

  select * into v_prior
  from private.payment_production_fulfillment_events
  where action_key=p_action_key;
  if found then
    return jsonb_build_object(
      'ok',v_prior.status='fulfilled',
      'duplicate',true,
      'status',v_prior.status,
      'order_id',v_prior.order_id,
      'action_key',v_prior.action_key
    );
  end if;

  select * into v_order
  from private.payment_production_orders
  where id=p_order_id
  for update;
  if not found then raise exception 'order not found'; end if;

  if v_order.environment<>'production'
     or v_order.adapter_key<>'billplz-payment-v1'
     or v_order.purpose<>'commercial_order' then
    raise exception 'production commercial order required';
  end if;
  if v_order.status<>'paid' or v_order.paid_at is null then
    raise exception 'verified paid order required';
  end if;
  if v_order.fulfillment_state='fulfilled' then
    return jsonb_build_object(
      'ok',true,'duplicate',true,'status','fulfilled','order_id',v_order.id
    );
  end if;
  if v_order.fulfillment_state<>'unfulfilled' then
    raise exception 'invalid fulfillment state';
  end if;

  select exists(
    select 1
    from private.payment_production_webhook_events e
    where e.provider_bill_id=v_order.provider_bill_id
      and e.signature_valid=true
      and e.normalized_status='paid'
      and e.amount_minor=v_order.amount_minor
      and e.applied=true
      and coalesce(e.error_text,'')=''
  ) into v_signed_paid;
  if not v_signed_paid then raise exception 'signed paid webhook evidence required'; end if;

  insert into private.commercial_order_documents(
    order_id,document_type,reference,amount_minor,currency,status,issued_by,metadata
  ) values (
    v_order.id,'receipt',v_receipt,v_order.amount_minor,v_order.currency,'issued',v_uid,
    jsonb_build_object(
      'payment_provider','billplz',
      'provider_bill_id',v_order.provider_bill_id,
      'merchant_reference',v_order.merchant_reference,
      'payment_verified',true,
      'tax_einvoice_claim',false
    )
  );

  if v_invoice<>'' then
    insert into private.commercial_order_documents(
      order_id,document_type,reference,amount_minor,currency,status,issued_by,metadata
    ) values (
      v_order.id,'invoice',v_invoice,v_order.amount_minor,v_order.currency,'issued',v_uid,
      jsonb_build_object(
        'merchant_reference',v_order.merchant_reference,
        'accounting_reference_only',true,
        'tax_einvoice_claim',false
      )
    );
  end if;

  update private.payment_production_orders
  set fulfillment_state='fulfilled',
      updated_at=now(),
      metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'fulfilled_by',v_uid,
        'fulfilled_at',now(),
        'receipt_reference',v_receipt,
        'invoice_reference',nullif(v_invoice,''),
        'human_fulfillment_approval',true,
        'authenticator_assurance_level',v_aal
      )
  where id=v_order.id and fulfillment_state='unfulfilled';
  if not found then raise exception 'fulfillment race blocked'; end if;

  insert into private.payment_production_fulfillment_events(
    order_id,action_key,status,reason,evidence
  ) values (
    v_order.id,p_action_key,'fulfilled',
    coalesce(nullif(trim(p_rationale),''),'Explicit owner/admin commercial fulfilment'),
    jsonb_build_object(
      'provider_bill_id',v_order.provider_bill_id,
      'amount_minor',v_order.amount_minor,
      'currency',v_order.currency,
      'payment_status','paid',
      'signed_webhook_required',true,
      'signed_webhook_verified',true,
      'receipt_reference',v_receipt,
      'invoice_reference',nullif(v_invoice,''),
      'delivery_evidence',coalesce(p_delivery_evidence,'{}'::jsonb),
      'fulfilled_by',v_uid,
      'authenticator_assurance_level',v_aal,
      'mfa_enforced',true,
      'environment','production'
    )
  );

  return jsonb_build_object(
    'ok',true,'duplicate',false,'status','fulfilled',
    'order_id',v_order.id,'receipt_reference',v_receipt,
    'invoice_reference',nullif(v_invoice,'')
  );
end;
$$;

revoke all on function public.vl_fulfill_commercial_order(uuid,text,text,text,jsonb,text)
  from public,anon;
grant execute on function public.vl_fulfill_commercial_order(uuid,text,text,text,jsonb,text)
  to authenticated;

create or replace function public.vl_close_commercial_order(
  p_order_id uuid,
  p_rationale text default null
)
returns jsonb
language plpgsql
security definer
set search_path=private,public,extensions,pg_temp
as $$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  v_is_operator boolean:=false;
  v_order private.payment_production_orders%rowtype;
  v_doc_count int:=0;
  v_fulfilled_event boolean:=false;
begin
  if v_uid is null then raise exception 'authenticated operator required'; end if;
  if v_aal<>'aal2' then raise exception 'AAL2 MFA required for commercial close'; end if;

  select exists(
    select 1 from public.project_members pm
    where pm.user_id=v_uid and pm.role in ('owner','admin')
  ) into v_is_operator;
  if not v_is_operator then raise exception 'owner/admin close approval required'; end if;

  select * into v_order
  from private.payment_production_orders
  where id=p_order_id
  for update;
  if not found then raise exception 'order not found'; end if;

  if v_order.purpose<>'commercial_order'
     or v_order.status<>'paid'
     or v_order.fulfillment_state<>'fulfilled' then
    raise exception 'paid fulfilled commercial order required';
  end if;

  if exists(select 1 from private.commercial_order_closures c where c.order_id=v_order.id) then
    return jsonb_build_object('ok',true,'duplicate',true,'status','closed','order_id',v_order.id);
  end if;

  select count(*) into v_doc_count
  from private.commercial_order_documents d
  where d.order_id=v_order.id and d.status='issued' and d.document_type='receipt';
  if v_doc_count<1 then raise exception 'issued receipt evidence required'; end if;

  select exists(
    select 1 from private.payment_production_fulfillment_events f
    where f.order_id=v_order.id and f.status='fulfilled'
  ) into v_fulfilled_event;
  if not v_fulfilled_event then raise exception 'fulfilment event evidence required'; end if;

  insert into private.commercial_order_closures(order_id,closed_by,rationale,evidence)
  values(
    v_order.id,v_uid,coalesce(nullif(trim(p_rationale),''),'Commercial order completed and closed'),
    jsonb_build_object(
      'payment_status',v_order.status,
      'fulfillment_state',v_order.fulfillment_state,
      'receipt_evidence',true,
      'fulfillment_event_evidence',true,
      'authenticator_assurance_level',v_aal,
      'mfa_enforced',true
    )
  );

  update private.payment_production_orders
  set updated_at=now(),
      metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'commercial_closed',true,
        'commercial_closed_at',now(),
        'commercial_closed_by',v_uid
      )
  where id=v_order.id;

  return jsonb_build_object('ok',true,'duplicate',false,'status','closed','order_id',v_order.id);
end;
$$;

revoke all on function public.vl_close_commercial_order(uuid,text)
  from public,anon;
grant execute on function public.vl_close_commercial_order(uuid,text)
  to authenticated;

commit;
