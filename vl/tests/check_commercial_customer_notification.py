#!/usr/bin/env python3
from pathlib import Path
import sys

send=Path("vl/functions/vl-commercial-notify-production/index.ts").read_text()
webhook=Path("vl/functions/vl-resend-webhook-production/index.ts").read_text()
sql=Path("vl/migrations/20260918_commercial_customer_notification.sql").read_text()
errors=[]

def need(label,text,token):
    if token not in text: errors.append(f"{label}: missing {token}")
def forbid(label,text,token):
    if token in text: errors.append(f"{label}: forbidden {token}")

for token in [
    "RESEND_PRODUCTION_API_KEY",
    "RESEND_PRODUCTION_FROM",
    'jwtClaim(token,"aal")!=="aal2"',
    '.in("role",["owner","admin"])',
    "get_vrs_notification_production_readiness",
    'production_send_allowed',
    'adapter_status!=="active"',
    'payment_confirmed',
    'order_fulfilled',
    'order_closed',
    'sb.auth.admin.getUserById',
    'lds-commercial:',
    'Idempotency-Key',
    'sha256(to)',
    'recipient_pii_stored:false',
    'vl_record_commercial_notification_send',
]:
    need("send",send,token)

for token in [
    "RESEND_PRODUCTION_WEBHOOK_SECRET",
    'Webhook',
    'invalid webhook signature',
    'resend-prod:',
    'vl_apply_resend_production_webhook',
]:
    need("webhook",webhook,token)

for token in [
    "'production'::text",
    "vl_record_commercial_notification_send",
    "environment='production'",
    "pii_stored',false",
    "production_send',true",
    "apply_resend_production_webhook",
    "signature_valid",
    "grant execute on function public.vl_record_commercial_notification_send",
    "to service_role",
]:
    need("migration",sql,token)

for token in [
    "metadata->>'email'",
    "recipient_email",
    "grant execute on function public.vl_record_commercial_notification_send(uuid,text,text,text,text,text,uuid)\n  to authenticated",
]:
    forbid("migration",sql,token)

if errors:
    print("Commercial customer notification contract: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("Commercial customer notification contract: PASS")
