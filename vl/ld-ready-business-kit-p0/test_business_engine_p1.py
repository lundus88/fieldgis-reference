import json
from pathlib import Path

from business_engine_p1 import (
    SURFACE_REGISTRY,
    compose_integration_plan,
    request_action,
    validate_surface_registry,
)

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def load(path):
    return json.loads((ROOT / path).read_text())

def tenant():
    return load("platform-config/tenant-property-demo.json")

def pack():
    return load("industry-packs/property-broker.json")

def actor(t, role="VIEWER"):
    return {
        "principal_id": "p1-user-demo",
        "membership_evidence": {
            "verified": True,
            "evidence_ref": "membership-evidence-p1-demo",
            "organization_ref": t["organization_ref"],
            "role": role,
        },
    }

def test_surface_registry_is_valid_and_reuse_only():
    out = validate_surface_registry()
    assert out["decision"] == "ALLOW"
    assert len(out["registry_digest"]) == 64
    assert all(v["execution_authority"] in {"NONE", "EXISTING_GATES_ONLY"} for v in SURFACE_REGISTRY.values())

def test_all_registered_sources_and_contracts_exist():
    for entry in SURFACE_REGISTRY.values():
        assert (REPO / entry["source"]).is_file(), entry["source"]
        assert (REPO / entry["contract"]).is_file(), entry["contract"]

def test_external_contracts_keep_production_disabled():
    contracts = [
        "commercial/lundus-digital-systems/client-portal-contract.json",
        "docs/commercial/lds-pricing-estimation-intelligence/contract.json",
        "docs/commercial/lds-project-profitability-capacity/contract.json",
        "docs/commercial/lds-executive-commercial-mission-control/contract.json",
    ]
    for rel in contracts:
        data = json.loads((REPO / rel).read_text())
        assert data.get("production_activation_authorized") is False, rel

def test_property_business_tenant_can_compose_existing_surfaces():
    t = tenant()
    out = compose_integration_plan(
        t,
        pack(),
        actor(t),
        [
            "CUSTOMER_PORTAL",
            "DELIVERY_FACTORY",
            "PRICING_INTELLIGENCE",
            "PROFITABILITY_CAPACITY",
            "EXECUTIVE_MISSION_CONTROL",
        ],
    )
    assert out["decision"] == "ALLOW"
    assert out["plan"]["production"] == "LOCKED"
    assert out["plan"]["live_charging"] == "LOCKED"
    assert out["plan"]["new_generic_engines"] == []
    assert all(b["action"] == "REUSE" for b in out["plan"]["surfaces"])

def test_cross_tenant_actor_cannot_get_integration_plan():
    t = tenant()
    a = actor(t)
    a["membership_evidence"]["organization_ref"] = "foreign-org"
    out = compose_integration_plan(t, pack(), a, ["CUSTOMER_PORTAL"])
    assert out["decision"] == "HOLD"
    assert out["reason"] == "CROSS_TENANT_ACCESS_DENIED"

def test_unknown_surface_fails_closed():
    t = tenant()
    out = compose_integration_plan(t, pack(), actor(t), ["NEW_DUPLICATE_CRM"])
    assert out["decision"] == "HOLD"
    assert out["reason"] == "INTEGRATION_SURFACE_UNKNOWN"

def test_surface_requires_pack_capability():
    t = tenant()
    p = pack()
    p["capabilities"] = [c for c in p["capabilities"] if c != "PAYMENT"]
    out = compose_integration_plan(t, p, actor(t), ["CUSTOMER_PORTAL"])
    assert out["decision"] == "HOLD"

def test_integration_layer_never_executes_human_only_actions():
    t = tenant()
    plan = compose_integration_plan(t, pack(), actor(t), ["CUSTOMER_PORTAL"])
    assert plan["decision"] == "ALLOW"
    for action in [
        "FINAL_PRICE_APPROVAL",
        "CUSTOMER_QUOTATION_RELEASE",
        "LIVE_CHARGE",
        "PRODUCTION_DEPLOY",
        "PRIVILEGE_WIDENING",
    ]:
        out = request_action(plan, action)
        assert out["decision"] == "HUMAN_GATE"
        assert out["automatic_execution"] is False

def test_unknown_action_is_not_implicitly_allowed():
    t = tenant()
    plan = compose_integration_plan(t, pack(), actor(t), ["CUSTOMER_PORTAL"])
    out = request_action(plan, "DO_SOMETHING_NEW")
    assert out["decision"] == "HOLD"
    assert out["automatic_execution"] is False

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LD Business Engine P1 integration tests")
