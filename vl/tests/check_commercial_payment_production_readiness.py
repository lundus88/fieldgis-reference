#!/usr/bin/env python3
from pathlib import Path
import sys

create = Path("vl/functions/vl-billplz-create-production/index.ts").read_text()
webhook = Path("vl/functions/vl-billplz-webhook-production/index.ts").read_text()
migration = Path("vl/migrations/20260918_commercial_payment_production_readiness.sql").read_text()

errors = []

def need(label, text, token):
    if token not in text:
        errors.append(f"{label}: missing {token}")

def forbid(label, text, token):
    if token in text:
        errors.append(f"{label}: forbidden {token}")

for token in [
    'schema("private")',
    'from("commercial_offers")',
    '.eq("status", "active")',
    'offer.customer_account_id !== account.id',
    'offer.valid_until',
    'active order already exists for this offer',
    'amount_source: "server_offer_catalog"',
    'client_amount_accepted: false',
    'purpose: "commercial_order"',
    'offer_key: offer.offer_key',
    'customer_account_id: account.id',
    'LUNDUS_COMMERCIAL_ORIGIN',
    'origin !== ALLOWED_ORIGIN',
    'terms_accepted_at',
    'payment_status: "pending"',
    'fulfillment_state: "unfulfilled"',
]:
    need("create", create, token)

for token in ["body.amount", "b.amount"]:
    forbid("create", create, token)

# Order reservation must happen before external provider bill creation.
reservation = create.find('from("payment_production_orders")')
provider = create.find('fetch("https://www.billplz.com/api/v3/bills"')
if reservation < 0 or provider < 0 or reservation > provider:
    errors.append("create: provider bill is attempted before authoritative order reservation")

for token in [
    "BILLPLZ_X_SIGNATURE_KEY",
    "hmacHex",
    "equalConst",
    "vl_apply_billplz_production_webhook",
    "invalid signature",
    "amount mismatch",
]:
    need("webhook", webhook, token)

for token in [
    "private.commercial_offers",
    "offer_type",
    "customer_account_id uuid references public.customer_accounts(id)",
    "valid_until timestamptz",
    "payment_production_orders_active_customer_offer_uq",
    "add column if not exists offer_key",
    "add column if not exists customer_account_id",
    "revoke all on private.commercial_offers from public, anon, authenticated",
    "current_user not in ('service_role','postgres')",
    "fulfillment_separated",
    "pending_to_paid_awaiting_fulfillment",
    "duplicate_event",
    "terminal_order_not_resurrected",
]:
    need("migration", migration, token)

forbid("migration", migration, "set status='paid',paid_at=coalesce(paid_at,now()),fulfillment_state='fulfilled'")

if errors:
    print("Commercial payment production readiness contract: FAIL")
    for e in errors:
        print("-", e)
    sys.exit(1)

print("Commercial payment production readiness contract: PASS")
