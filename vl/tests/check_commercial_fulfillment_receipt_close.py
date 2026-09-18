#!/usr/bin/env python3
from pathlib import Path
import sys

sql=Path("vl/migrations/20260918_commercial_fulfillment_receipt_close.sql").read_text()
errors=[]

def need(token):
    if token not in sql:
        errors.append(f"missing: {token}")

def forbid(token):
    if token in sql:
        errors.append(f"forbidden: {token}")

for token in [
    "private.commercial_order_documents",
    "private.commercial_order_closures",
    "public.vl_fulfill_commercial_order",
    "public.vl_close_commercial_order",
    "AAL2 MFA required for commercial fulfilment",
    "AAL2 MFA required for commercial close",
    "pm.role in ('owner','admin')",
    "signed paid webhook evidence required",
    "signature_valid=true",
    "normalized_status='paid'",
    "e.amount_minor=v_order.amount_minor",
    "e.applied=true",
    "payment_production_fulfillment_events",
    "action_key=p_action_key",
    "document_type in ('receipt','invoice')",
    "tax_einvoice_claim',false",
    "human_fulfillment_approval',true",
    "issued receipt evidence required",
    "fulfilment event evidence required",
    "commercial_closed',true",
    "revoke all on function public.vl_fulfill_commercial_order",
    "revoke all on function public.vl_close_commercial_order",
]:
    need(token)

for token in [
    "grant execute on function public.vl_fulfill_commercial_order(uuid,text,text,text,jsonb,text) to anon",
    "grant execute on function public.vl_close_commercial_order(uuid,text) to anon",
    "fulfillment_state='fulfilled',paid_at=",
]:
    forbid(token)

if errors:
    print("Commercial fulfillment receipt close contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("Commercial fulfillment receipt close contract: PASS")
