from ai_site_intelligence import compile_prompt_to_sitespec, generate_prompt_preview

BASE = {
    "prompt": "Bina website premium untuk cafe tempatan. Fokus pada menu dan WhatsApp.",
    "business_name": "Kopi Contoh",
    "whatsapp": "60123456789",
    "items": [
        {"name": "Latte", "price": "RM8", "description": "Kopi susu."},
        {"name": "Nasi Lemak", "price": "RM10", "description": "Sarapan."},
    ],
}

def test_prompt_compiles_to_sitespec():
    out = compile_prompt_to_sitespec(BASE)
    assert out["decision"] == "ALLOW"
    assert out["sitespec"]["schema"] == "ld.ai-site-spec/1"
    assert out["sitespec"]["source_mode"] == "PROMPT"
    assert out["sitespec"]["vertical"] == "cafe"
    assert out["sitespec"]["authority"]["production_publish"] == "HUMAN_ONLY"

def test_prompt_preview_reuses_existing_renderer():
    out = generate_prompt_preview(BASE)
    assert out["decision"] == "ALLOW"
    assert "<!doctype html>" in out["preview_html"].lower()
    assert out["preview_manifest"]["production"] == "LOCKED"
    assert out["human_approval_required"] is True


def test_property_vertical_reuses_existing_renderer():
    req = {
        "prompt": "Bina website premium untuk broker tanah dengan listing dan WhatsApp.",
        "business_name": "TanahPro Demo",
        "whatsapp": "60123456789",
        "listings": [
            {"name": "Tanah Pertanian", "price": "RM320,000", "description": "Preview sahaja."}
        ],
    }
    out = generate_prompt_preview(req)
    assert out["decision"] == "ALLOW"
    assert out["sitespec"]["vertical"] == "property"
    assert out["preview_manifest"]["production"] == "LOCKED"
    assert "Senarai Hartanah" in out["preview_html"]

def test_missing_business_facts_fails_closed():
    bad = dict(BASE)
    bad.pop("whatsapp")
    out = compile_prompt_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "BUSINESS_FACTS_REQUIRED"

def test_ambiguous_vertical_fails_closed():
    bad = dict(BASE)
    bad["prompt"] = "Bina laman perniagaan moden."
    out = compile_prompt_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "VERTICAL_UNRESOLVED"

def test_missing_vertical_content_fails_closed():
    bad = dict(BASE)
    bad.pop("items")
    out = compile_prompt_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "VERTICAL_CONTENT_INVALID"

def test_deterministic_sitespec():
    a = compile_prompt_to_sitespec(BASE)
    b = compile_prompt_to_sitespec(BASE)
    assert a["sitespec"] == b["sitespec"]

def test_explicit_unsupported_vertical_fails_closed():
    bad = dict(BASE)
    bad["vertical"] = "clinic"
    out = compile_prompt_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "VERTICAL_UNRESOLVED"

def test_unsafe_optional_url_fails_closed():
    bad = dict(BASE)
    bad["social_url"] = "javascript:alert(1)"
    out = compile_prompt_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "UNSAFE_URL"
    assert out["field"] == "social_url"

def test_non_dict_cards_fail_closed():
    bad = dict(BASE)
    bad["items"] = ["Latte"]
    out = compile_prompt_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "VERTICAL_CONTENT_INVALID"

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"PASS {len(tests)} LD AI Site Intelligence P0 tests")
