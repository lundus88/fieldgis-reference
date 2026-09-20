#!/usr/bin/env python3
from dataclasses import dataclass
from pathlib import Path
import json
import sys

class Blocked(Exception):
    pass

@dataclass
class Lead:
    submission_id: str
    name: str
    email: str
    service: str
    message: str
    status: str = "New Lead"

@dataclass
class Quote:
    quote_id: str
    lead_id: str
    amount_minor: int
    currency: str
    human_approved: bool
    accepted: bool = False

seen_submissions=set()

def receive_lead(payload, *, origin, allowed_origin, enabled, turnstile_ok, honeypot=""):
    if not enabled:
        raise Blocked("lead intake disabled")
    if origin != allowed_origin:
        raise Blocked("origin mismatch")
    if not turnstile_ok:
        raise Blocked("turnstile verification required")
    if honeypot:
        raise Blocked("honeypot triggered")
    if len(json.dumps(payload)) > 16384:
        raise Blocked("payload too large")
    for key in ("submission_id","name","email","service","message","turnstile_token"):
        if not str(payload.get(key,"")).strip():
            raise Blocked(f"missing {key}")
    sid=payload["submission_id"]
    if sid in seen_submissions:
        return "duplicate"
    seen_submissions.add(sid)
    return Lead(sid,payload["name"],payload["email"],payload["service"],payload["message"])

def qualify(lead, *, human_reviewed):
    if not human_reviewed:
        raise Blocked("human review required before commercial qualification")
    lead.status="QUALIFIED"
    return lead

def issue_quote(lead, *, amount_minor, human_approved):
    if lead.status!="QUALIFIED":
        raise Blocked("qualified lead required")
    if not human_approved:
        raise Blocked("human-approved quotation required")
    if not isinstance(amount_minor,int) or amount_minor<=0:
        raise Blocked("invalid quote amount")
    return Quote("quote-001",lead.submission_id,amount_minor,"MYR",True)

def accept_quote(quote, *, customer_accepts):
    if not customer_accepts:
        raise Blocked("customer acceptance required")
    quote.accepted=True
    return quote

def create_order_from_quote(quote, *, browser_amount=None):
    if not quote.accepted or not quote.human_approved:
        raise Blocked("accepted human-approved quote required")
    # Browser amount is intentionally ignored.
    return {
        "order_id":"order-001",
        "quote_id":quote.quote_id,
        "amount_minor":quote.amount_minor,
        "currency":quote.currency,
        "status":"pending",
    }

def expect_block(label, fn):
    try:
        fn()
    except Blocked:
        return
    raise AssertionError(f"{label}: expected BLOCKED")

def contract_checks():
    root=Path("commercial/lundus-digital-systems")
    lead=json.loads((root/"lead-intake-contract.json").read_text())
    assess=json.loads((root/"workflow-assessment-contract.json").read_text())
    assert lead["client_to_lunduslead_direct_write"] is False
    for key in [
        "explicit_enable_flag","exact_origin_allowlist","turnstile_verification",
        "payload_size_limit","field_validation","owner_binding",
        "service_role_backend_only","idempotency_key","source_attribution"
    ]:
        assert key in lead["server_controls"], key
    for action in ["auto_quotation","auto_pricing","auto_payment","auto_sale","direct_browser_write_to_internal_crm"]:
        assert action in lead["forbidden_actions"], action
        assert action in assess["forbidden_actions"], action
    assert assess["production_activation_authorized"] is False

def run():
    contract_checks()
    allowed="https://lundusdigital.com"
    payload={
        "submission_id":"sub-001",
        "name":"Synthetic Customer",
        "email":"synthetic@example.invalid",
        "service":"Custom Digital Systems & Automation",
        "message":"Synthetic non-production prelaunch test.",
        "turnstile_token":"synthetic-pass"
    }

    expect_block("disabled intake",lambda:receive_lead(payload,origin=allowed,allowed_origin=allowed,enabled=False,turnstile_ok=True))
    expect_block("wrong origin",lambda:receive_lead(payload,origin="https://evil.example",allowed_origin=allowed,enabled=True,turnstile_ok=True))
    expect_block("turnstile",lambda:receive_lead(payload,origin=allowed,allowed_origin=allowed,enabled=True,turnstile_ok=False))
    expect_block("honeypot",lambda:receive_lead(payload,origin=allowed,allowed_origin=allowed,enabled=True,turnstile_ok=True,honeypot="spam"))

    lead=receive_lead(payload,origin=allowed,allowed_origin=allowed,enabled=True,turnstile_ok=True)
    assert isinstance(lead,Lead)
    assert receive_lead(payload,origin=allowed,allowed_origin=allowed,enabled=True,turnstile_ok=True)=="duplicate"

    expect_block("qualification without review",lambda:qualify(lead,human_reviewed=False))
    qualify(lead,human_reviewed=True)

    expect_block("auto quote",lambda:issue_quote(lead,amount_minor=49700,human_approved=False))
    quote=issue_quote(lead,amount_minor=49700,human_approved=True)
    expect_block("quote not accepted",lambda:create_order_from_quote(quote,browser_amount=1))
    accept_quote(quote,customer_accepts=True)
    order=create_order_from_quote(quote,browser_amount=1)
    assert order["amount_minor"]==49700
    assert order["currency"]=="MYR"

    print("LD Prelaunch Synthetic Lead-to-Order: PASS")
    print("lead intake fail-closed: PASS")
    print("origin / Turnstile / honeypot: PASS")
    print("submission idempotency: PASS")
    print("human qualification gate: PASS")
    print("human quotation gate: PASS")
    print("customer acceptance gate: PASS")
    print("server-authoritative amount: PASS")
    print("external API calls: NONE")
    print("live lead write: NONE")
    print("live payment: NONE")

if __name__=="__main__":
    try:
        run()
    except Exception as exc:
        print("LD Prelaunch Synthetic Lead-to-Order: FAIL")
        print(type(exc).__name__,str(exc))
        sys.exit(1)
