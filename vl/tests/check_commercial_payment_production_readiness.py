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

need("create", create, 'schema("private").from("commercial_offers")')
need("create", create, '.eq("status", "active")')
need("create", create, 'amount_source: "server_offer_catalog"')
need("create", create, 'client_amount_accepted: false')
need("create", create, 'purpose: "commercial_order"')
need("create", create, 'LUNDUS_COMMERCIAL_ORIGIN')
need("create", create, 'origin !== ALLOWED_ORIGIN')
need("create", create, 'terms_accepted_at')
need("create", create, 'payment_status: "pending"')
need("create", create, 'fulfillment_state: "unfulfilled"')
forbid("create", create, "body.amount")
forbid("create", create, "b.amount")

need("webhook", webhook, "BILLPLZ_X_SIGNATURE_KEY")
need("webhook", webhook, "hmacHex")
need("webhook", webhook, "equalConst")
need("webhook", webhook, 'vl_apply_billplz_production_webhook')
need("webhook", webhook, 'invalid signature')
need("webhook", webhook, 'amount mismatch')

need("migration", migration, "private.commercial_offers")
need("migration", migration, "revoke all on private.commercial_offers from public, anon, authenticated")
need("migration", migration, "current_user not in ('service_role','postgres')")
need("migration", migration, "fulfillment_separated")
need("migration", migration, "pending_to_paid_awaiting_fulfillment")
need("migration", migration, "duplicate_event")
need("migration", migration, "terminal_order_not_resurrected")
forbid("migration", migration, "set status='paid',paid_at=coalesce(paid_at,now()),fulfillment_state='fulfilled'")

if errors:
    print("Commercial payment production readiness contract: FAIL")
    for e in errors:
        print("-", e)
    sys.exit(1)

print("Commercial payment production readiness contract: PASS")
