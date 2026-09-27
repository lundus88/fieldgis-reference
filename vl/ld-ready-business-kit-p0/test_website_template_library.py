from website_template_library import (
    TEMPLATES,
    library_manifest,
    recommend_lane,
    resolve_template,
    validate_template,
)

def test_six_flagship_templates_are_valid():
    assert len(TEMPLATES) == 6
    for template in TEMPLATES.values():
        assert validate_template(template)["decision"] == "ALLOW"

def test_manifest_is_deterministic_and_locked():
    a = library_manifest()
    b = library_manifest()
    assert a == b
    assert a["decision"] == "ALLOW"
    assert a["production"] == "LOCKED"
    assert a["customer_commitment"] == "HUMAN_ONLY"
    assert a["pricing"] == "HUMAN_ONLY"

def test_each_template_has_conversion_path():
    for template in TEMPLATES.values():
        caps = set(template["capabilities"])
        assert "WHATSAPP_CTA" in caps
        assert "LEAD_CAPTURE" in caps
        assert {"hero","trust","offer","process","cta"}.issubset(set(template["sections"]))

def test_express_templates_exist_without_unconditional_guarantee():
    manifest = library_manifest()
    express = [x for x in manifest["templates"] if x["delivery_lane"] == "EXPRESS_24H"]
    assert express
    assert "not unconditional guarantees" in manifest["promise_policy"]

def test_lane_requires_ready_inputs_and_locked_scope():
    assert recommend_lane("sme-corporate", False, True)["decision"] == "HOLD"
    assert recommend_lane("sme-corporate", True, False)["decision"] == "HOLD"
    allowed = recommend_lane("sme-corporate", True, True)
    assert allowed["decision"] == "ALLOW"
    assert allowed["delivery_lane"] == "EXPRESS_24H"
    assert allowed["commitment"] == "TARGET_ONLY"
    assert allowed["human_quote_and_commitment_required"] is True

def test_unknown_template_fails_closed():
    assert resolve_template("unknown")["reason"] == "TEMPLATE_NOT_FOUND"

if __name__ == "__main__":
    tests = [v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"PASS {len(tests)} LD website template library tests")
