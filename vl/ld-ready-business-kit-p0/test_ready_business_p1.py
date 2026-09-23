import json
from pathlib import Path

from ready_business_p1 import (
    create_client_project,
    approve_pricing,
    authorize_customer_release,
    record_customer_acceptance,
    delivery_manifest,
)

ROOT=Path(__file__).resolve().parent

def sample(name="cafe.json"):
    return json.loads((ROOT/"verticals"/name).read_text())

def test_client_project_to_delivery_prep():
    p=create_client_project(sample(),"starter")
    assert p["decision"]=="ALLOW"
    assert p["quotation"]["amount"] is None
    assert p["quotation"]["payment_request"]=="DISABLED"
    assert p["workspace"]["production"]=="LOCKED"
    assert p["workspace"]["state"]=="WAITING_HUMAN_COMMERCIAL_APPROVAL"

    denied=approve_pricing(p,{"decision":"APPROVE","amount":199})
    assert denied["decision"]=="HUMAN_GATE"

    p=approve_pricing(p,{"decision":"APPROVE","amount":199,"human_approver":"fixture-owner"})
    assert p["quotation"]["amount"]==199
    assert p["workspace"]["state"]=="WAITING_HUMAN_CUSTOMER_RELEASE"

    denied=authorize_customer_release(p,{"decision":"APPROVE"})
    assert denied["decision"]=="HUMAN_GATE"

    p=authorize_customer_release(p,{"decision":"APPROVE","human_approver":"fixture-owner"})
    assert p["workspace"]["state"]=="READY_FOR_CUSTOMER_REVIEW"

    denied=record_customer_acceptance(p,{"accepted":True})
    assert denied["decision"]=="HOLD"

    p=record_customer_acceptance(p,{"accepted":True,"evidence_ref":"fixture:customer-acceptance"})
    assert p["workspace"]["state"]=="READY_FOR_DELIVERY_PREP"

    m=delivery_manifest(p)
    assert m["decision"]=="ALLOW"
    assert m["payment"]=="DISABLED"
    assert m["production"]=="LOCKED"
    assert m["production_publish"]=="HUMAN_ONLY"

def test_all_verticals_create_project():
    ids=set()
    for name in ["cafe.json","homestay.json","tutor.json"]:
        p=create_client_project(sample(name),"starter")
        assert p["decision"]=="ALLOW"
        ids.add(p["project_id"])
    assert len(ids)==3

def test_invalid_onboarding_stays_closed():
    d=sample()
    d["whatsapp"]=""
    p=create_client_project(d,"starter")
    assert p["decision"]=="HOLD"

def test_unknown_package_holds():
    p=create_client_project(sample(),"enterprise-unapproved")
    assert p["decision"]=="HOLD"

def test_delivery_cannot_skip_human_gates():
    p=create_client_project(sample(),"starter")
    assert delivery_manifest(p)["decision"]=="HOLD"
    assert record_customer_acceptance(p,{"accepted":True,"evidence_ref":"x"})["decision"]=="HOLD"

if __name__=="__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:t()
    print(f"PASS {len(tests)} LD Ready Business Kit P1 tests")
