#!/usr/bin/env python3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
import sys

class Blocked(Exception):
    pass

@dataclass
class Customer:
    id: str
    terms_accepted: bool = True

@dataclass
class Offer:
    key: str
    customer_id: str
    amount_minor: int
    currency: str = "MYR"
    status: str = "active"
    valid_until: datetime = field(default_factory=lambda: datetime.now(timezone.utc)+timedelta(days=7))

@dataclass
class Order:
    id: str
    customer_id: str
    offer_key: str
    amount_minor: int
    currency: str
    status: str = "pending"
    fulfillment_state: str = "unfulfilled"
    provider_bill_id: Optional[str] = None
    receipt_reference: Optional[str] = None
    invoice_reference: Optional[str] = None
    closed: bool = False
    webhook_events: set = field(default_factory=set)
    notifications: set = field(default_factory=set)
    fulfillment_actions: set = field(default_factory=set)

def create_order(customer, offer, browser_amount=None):
    if not customer.terms_accepted:
        raise Blocked("terms required")
    if offer.status != "active":
        raise Blocked("offer inactive")
    if offer.customer_id != customer.id:
        raise Blocked("offer not assigned to customer")
    if offer.valid_until <= datetime.now(timezone.utc):
        raise Blocked("offer expired")
    if offer.currency != "MYR" or offer.amount_minor <= 0:
        raise Blocked("offer invariant failed")
    # browser_amount intentionally ignored: server-authoritative offer amount wins
    return Order(
        id="order-001",
        customer_id=customer.id,
        offer_key=offer.key,
        amount_minor=offer.amount_minor,
        currency=offer.currency
    )

def attach_provider_bill(order, provider_bill_id):
    if order.status != "pending":
        raise Blocked("order not pending")
    if order.provider_bill_id:
        raise Blocked("provider bill already attached")
    order.provider_bill_id = provider_bill_id

def apply_paid_webhook(order, event_key, provider_bill_id, amount_minor, signature_valid):
    if event_key in order.webhook_events:
        return "duplicate"
    if not signature_valid:
        raise Blocked("invalid signature")
    if provider_bill_id != order.provider_bill_id:
        raise Blocked("unknown production bill")
    if amount_minor != order.amount_minor:
        raise Blocked("amount mismatch")
    if order.status in ("cancelled","refunded"):
        raise Blocked("terminal order not resurrected")
    order.webhook_events.add(event_key)
    if order.status == "pending":
        order.status = "paid"
        return "paid"
    return "unchanged"

def send_notification(order, kind, aal2=True, operator_role="owner"):
    if not aal2 or operator_role not in ("owner","admin"):
        raise Blocked("AAL2 owner/admin required")
    if kind == "payment_confirmed" and order.status != "paid":
        raise Blocked("paid order required")
    if kind == "order_fulfilled" and order.fulfillment_state != "fulfilled":
        raise Blocked("fulfilled order required")
    if kind == "order_closed" and not order.closed:
        raise Blocked("closed order required")
    key=f"{order.id}:{kind}"
    if key in order.notifications:
        return "duplicate"
    order.notifications.add(key)
    return "sent"

def fulfill(order, action_key, receipt_reference, delivery_evidence, aal2=True, operator_role="owner"):
    if not aal2 or operator_role not in ("owner","admin"):
        raise Blocked("AAL2 owner/admin required")
    if action_key in order.fulfillment_actions:
        return "duplicate"
    if order.status != "paid":
        raise Blocked("verified paid order required")
    if not order.webhook_events:
        raise Blocked("signed paid webhook evidence required")
    if order.fulfillment_state != "unfulfilled":
        raise Blocked("invalid fulfillment state")
    if not receipt_reference:
        raise Blocked("receipt required")
    if not isinstance(delivery_evidence, dict) or not delivery_evidence:
        raise Blocked("delivery evidence required")
    order.fulfillment_actions.add(action_key)
    order.receipt_reference = receipt_reference
    order.fulfillment_state = "fulfilled"
    return "fulfilled"

def close(order, aal2=True, operator_role="owner"):
    if not aal2 or operator_role not in ("owner","admin"):
        raise Blocked("AAL2 owner/admin required")
    if order.status != "paid" or order.fulfillment_state != "fulfilled":
        raise Blocked("paid fulfilled order required")
    if not order.receipt_reference:
        raise Blocked("receipt evidence required")
    order.closed = True
    return "closed"

def expect_block(label, fn):
    try:
        fn()
    except Blocked:
        return
    raise AssertionError(f"{label}: expected BLOCKED")

def run():
    customer=Customer("cust-A")
    other=Customer("cust-B")
    offer=Offer("offer-A","cust-A",49700)

    # 1. Customer-scoped offer and server-authoritative amount
    expect_block("wrong customer", lambda: create_order(other, offer))
    expired=Offer("offer-expired","cust-A",49700,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    expect_block("expired offer", lambda: create_order(customer, expired))

    order=create_order(customer, offer, browser_amount=1)
    assert order.amount_minor == 49700, "browser amount must not control charge"

    # 2. Provider bill reservation
    attach_provider_bill(order,"bill-001")
    expect_block("duplicate provider bill", lambda: attach_provider_bill(order,"bill-002"))

    # 3. Signed callback invariants
    expect_block("invalid signature", lambda: apply_paid_webhook(order,"evt-bad-sig","bill-001",49700,False))
    expect_block("amount mismatch", lambda: apply_paid_webhook(order,"evt-bad-amt","bill-001",1,True))
    assert apply_paid_webhook(order,"evt-paid","bill-001",49700,True) == "paid"
    assert apply_paid_webhook(order,"evt-paid","bill-001",49700,True) == "duplicate"
    assert order.status == "paid"

    # 4. Payment confirmation notification remains separate from fulfilment
    assert send_notification(order,"payment_confirmed") == "sent"
    assert order.fulfillment_state == "unfulfilled"
    assert send_notification(order,"payment_confirmed") == "duplicate"

    # 5. Fulfilment remains human-gated + evidence-backed
    expect_block("fulfil without MFA", lambda: fulfill(order,"act-001","RCP-001",{"delivered":True},aal2=False))
    expect_block("fulfil without evidence", lambda: fulfill(order,"act-001","RCP-001",{},aal2=True))
    assert fulfill(order,"act-001","RCP-001",{"delivered":True,"artifact":"demo-package"}) == "fulfilled"
    assert fulfill(order,"act-001","RCP-001",{"delivered":True}) == "duplicate"
    assert send_notification(order,"order_fulfilled") == "sent"

    # 6. Close requires fulfilled + receipt evidence
    assert close(order) == "closed"
    assert send_notification(order,"order_closed") == "sent"

    # 7. Negative pre-payment path
    second=create_order(customer, Offer("offer-B","cust-A",30000))
    attach_provider_bill(second,"bill-002")
    expect_block("fulfil unpaid", lambda: fulfill(second,"act-B","RCP-B",{"delivered":True}))
    expect_block("notify unpaid", lambda: send_notification(second,"payment_confirmed"))

    print("Commercial Golden Transaction dry-run: PASS")
    print("lead/quote stage: contract-only")
    print("offer/customer scope: PASS")
    print("server-authoritative amount: PASS")
    print("signed payment callback: PASS")
    print("duplicate webhook idempotency: PASS")
    print("payment/fulfilment separation: PASS")
    print("AAL2 human fulfilment: PASS")
    print("receipt evidence: PASS")
    print("customer notifications: PASS")
    print("order close: PASS")
    print("negative paths: PASS")
    print("LIVE CUSTOMER CHARGE: NOT PERFORMED")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("Commercial Golden Transaction dry-run: FAIL")
        print(type(e).__name__, str(e))
        sys.exit(1)
