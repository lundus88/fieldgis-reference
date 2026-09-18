# Commercial Customer Notification RC

Status: REVIEW CANDIDATE ONLY
Production deployment: NOT AUTHORISED

## Purpose
Provide controlled customer acknowledgement for:
- payment confirmed
- order fulfilled
- order closed

## Authority and privacy
- authenticated operator required
- AAL2 MFA required
- owner/admin role required
- existing notification production adapter must report active + production_send_allowed
- customer email is resolved server-side from Supabase Auth using the order's created_by user
- plaintext customer email is not written to notification_outbox
- only SHA-256 recipient hash is recorded
- provider message ID and idempotency key are recorded

## Delivery evidence
Resend production webhooks are verified with Svix using RESEND_PRODUCTION_WEBHOOK_SECRET.
Signed events update production outbox state and remain compatible with existing reconciliation logic.

## Templates
payment_confirmed requires paid order.
order_fulfilled requires fulfilled order.
order_closed requires commercial_closed evidence.

## Safety
This RC deliberately uses operator-triggered controlled sends for the first launch. It does not couple payment callback success to email delivery and does not auto-fulfil an order.

No Edge Function, migration, secret, or live customer send is performed by this RC.
