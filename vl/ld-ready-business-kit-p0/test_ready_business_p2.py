import json
from pathlib import Path

from ready_business_p2 import (
    create_intake_package,
    clone_manifest,
    plan_delivery,
    simulate_ten_customers,
)

ROOT=Path(__file__).resolve().parent

def fixture(name):
    return json.loads((ROOT/"verticals"/name).read_text())

def all_fixtures():
    return [fixture("cafe.json"),fixture("homestay.json"),fixture("tutor.json")]

def test_consent_required():
    r=create_intake_package(fixture("cafe.json"),contact_consent=False)
    assert r["decision"]=="HOLD"
    assert r["reason"]=="CONTACT_CONSENT_REQUIRED"

def test_clone_is_locked_and_secret_free():
    i=create_intake_package(
        fixture("homestay.json"),
        acquisition_source="referral",
        contact_consent=True,
    )
    c=clone_manifest(i)
    assert c["decision"]=="ALLOW"
    m=c["manifest"]
    assert m["production"]=="LOCKED"
    assert m["publish_authority"]=="HUMAN_ONLY"
    assert m["secrets_embedded"] is False
    assert m["features"]["payment"] is False
    assert m["domain"]["binding"]=="UNBOUND"

def test_capacity_governor():
    items=[]
    for name in ["cafe.json","homestay.json","tutor.json"]:
        items.append(create_intake_package(fixture(name),contact_consent=True))
    r=plan_delivery(items,daily_limit=2,concurrent_limit=1)
    assert r["decision"]=="ALLOW"
    assert r["estimated_delivery_days"]==2
    assert "MULTI_DAY_QUEUE" in r["bottlenecks"]
    assert "SERIAL_DELIVERY" in r["bottlenecks"]

def test_invalid_capacity_fails_closed():
    i=create_intake_package(fixture("cafe.json"),contact_consent=True)
    assert plan_delivery([i],daily_limit=0,concurrent_limit=1)["decision"]=="HOLD"
    assert plan_delivery([i],daily_limit=1,concurrent_limit=2)["decision"]=="HOLD"

def test_ten_customer_simulation():
    r=simulate_ten_customers(all_fixtures(),daily_limit=3,concurrent_limit=1)
    assert r["decision"]=="ALLOW"
    assert r["synthetic_only"] is True
    assert r["live_customers"] is False
    assert r["revenue_evidence"] is False
    assert r["payment_transactions"]==0
    assert r["production_deployments"]==0
    assert r["customer_count"]==10
    assert r["unique_project_ids"]==10
    assert r["unique_tenant_ids"]==10
    assert r["all_payment_disabled"] is True
    assert r["all_production_locked"] is True
    assert r["capacity_plan"]["estimated_delivery_days"]==4
    assert r["activation_authorized"] is False

if __name__=="__main__":
    ts=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in ts:t()
    print(f"PASS {len(ts)} LD Ready Business Kit P2 tests")
