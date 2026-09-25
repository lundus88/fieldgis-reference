import json
from pathlib import Path

from platform_foundation import (
    authorize_tenant_action,
    build_pack_registry,
    compose_tenant_runtime,
    evaluate_package_change,
    resolve_capabilities,
    resolve_entitlement,
    validate_capability_dependencies,
    validate_tenant,
)

ROOT = Path(__file__).resolve().parent

def load(path):
    return json.loads((ROOT / path).read_text())

def tenant():
    return load("platform-config/tenant-property-demo.json")

def pack():
    return load("industry-packs/property-broker.json")

def test_tenant_is_isolated_and_fail_closed():
    t = tenant()
    out = validate_tenant(t)
    assert out["decision"] == "ALLOW"
    assert len(out["digest"]) == 64
    t["production_write_authority"] = True
    assert validate_tenant(t)["reason"] == "TENANT_CANNOT_GRANT_PRODUCTION_WRITE"

def test_business_package_entitles_property_pack():
    out = resolve_entitlement(tenant(), pack()["capabilities"])
    assert out["decision"] == "ALLOW"
    assert out["production"] == "LOCKED"

def test_lower_package_cannot_silently_expand():
    t = tenant()
    t["package"] = "launch"
    out = resolve_entitlement(t, pack()["capabilities"])
    assert out["decision"] == "HOLD"
    assert out["reason"] == "ENTITLEMENT_DENIED"
    assert "LISTING" in out["denied"]

def test_industry_pack_registry_is_deterministic():
    a = build_pack_registry([pack()])
    b = build_pack_registry([pack()])
    assert a["decision"] == "ALLOW"
    assert a["registry_digest"] == b["registry_digest"]
    assert a["production"] == "LOCKED"

def test_duplicate_pack_id_fails_closed():
    out = build_pack_registry([pack(), pack()])
    assert out["decision"] == "HOLD"
    assert out["reason"] == "PACK_ID_DUPLICATE"

def test_capability_resolver_reuses_existing_owners():
    out = resolve_capabilities(pack()["capabilities"])
    assert out["decision"] == "ALLOW"
    assert out["build_new"] == []
    assert out["policy"] == "REUSE_BEFORE_BUILD"
    assert all(b["action"] == "REUSE" for b in out["bindings"])

def test_unknown_capability_requires_review_before_build():
    out = resolve_capabilities(["LEAD_CRM", "UNKNOWN_NEW_ENGINE"])
    assert out["decision"] == "HOLD"
    assert out["reason"] == "CAPABILITY_OWNER_UNKNOWN"
    assert out["action"] == "REVIEW_BEFORE_BUILD"

def test_composed_runtime_keeps_authority_locked():
    out = compose_tenant_runtime(tenant(), pack())
    assert out["decision"] == "ALLOW"
    assert out["production"] == "LOCKED"
    assert out["live_charging"] == "LOCKED"
    assert out["authority"]["production_deploy"] == "HUMAN_ONLY"


def test_cross_tenant_access_is_denied():
    t = tenant()
    actor = {"organization_ref": "another-org", "role": "OWNER"}
    out = authorize_tenant_action(t, actor, "VIEW")
    assert out["decision"] == "HOLD"
    assert out["reason"] == "CROSS_TENANT_ACCESS_DENIED"

def test_role_permissions_are_least_privilege():
    t = tenant()
    viewer = {"organization_ref": t["organization_ref"], "role": "VIEWER"}
    assert authorize_tenant_action(t, viewer, "VIEW")["decision"] == "ALLOW"
    denied = authorize_tenant_action(t, viewer, "OPERATE")
    assert denied["decision"] == "HOLD"
    assert denied["reason"] == "ROLE_PERMISSION_DENIED"

def test_role_access_never_grants_production_authority():
    t = tenant()
    owner = {"organization_ref": t["organization_ref"], "role": "OWNER"}
    out = authorize_tenant_action(t, owner, "CONFIGURE_PACK")
    assert out["decision"] == "ALLOW"
    assert out["production_authority"] is False
    assert out["live_charging_authority"] is False

def test_capability_dependencies_fail_closed():
    out = validate_capability_dependencies(["PAYMENT"])
    assert out["decision"] == "HOLD"
    assert out["reason"] == "CAPABILITY_DEPENDENCY_MISSING"
    assert "ORDER" in out["missing"]["PAYMENT"]

def test_package_change_is_always_human_gated_and_non_destructive():
    t = tenant()
    active = pack()["capabilities"]
    out = evaluate_package_change(t, "launch", active)
    assert out["decision"] == "HUMAN_GATE"
    assert out["automatic_upgrade_authorized"] is False
    assert out["data_deletion_authorized"] is False
    assert "LISTING" in out["capabilities_removed_from_entitlement"]

def test_tenant_pack_mismatch_fails_closed():
    t = tenant()
    t["industry_pack"] = "survey"
    out = compose_tenant_runtime(t, pack())
    assert out["decision"] == "HOLD"
    assert out["reason"] == "TENANT_PACK_MISMATCH"

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LD Business Platform Foundation P0 tests")
