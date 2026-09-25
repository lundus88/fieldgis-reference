from ai_site_intelligence import compile_url_reference_to_sitespec, generate_url_reference_preview

BASE = {
    "reference_url": "https://example.com/reference?utm_source=test#hero",
    "reference_snapshot": {
        "capture_mode": "APPROVED_READ_ONLY",
        "source_url": "https://example.com/reference",
        "section_types": ["hero", "services", "testimonials", "contact"],
        "style_hints": ["premium", "clean"],
        "layout_density": "balanced",
        "sticky_navigation": True,
        "floating_cta": True,
    },
    "vertical": "cafe",
    "business_name": "Kopi Contoh",
    "whatsapp": "60123456789",
    "items": [
        {"name": "Latte", "price": "RM8", "description": "Kopi susu."},
        {"name": "Nasi Lemak", "price": "RM10", "description": "Sarapan."},
    ],
}

def test_url_reference_compiles_to_sitespec():
    out = compile_url_reference_to_sitespec(BASE)
    assert out["decision"] == "ALLOW"
    spec = out["sitespec"]
    assert spec["source_mode"] == "URL_REFERENCE"
    assert spec["reference"]["url"] == "https://example.com/reference"
    assert spec["reference"]["query_stripped"] is True
    assert spec["reference"]["fragment_stripped"] is True
    assert spec["reference"]["structure_only"] is True
    assert spec["content_policy"]["reference_content_reuse"] is False
    assert spec["design_signals"]["section_types"] == ["hero", "services", "testimonials", "contact"]

def test_url_mode_can_operate_without_freeform_prompt_when_vertical_explicit():
    out = compile_url_reference_to_sitespec(BASE)
    assert out["decision"] == "ALLOW"
    assert out["sitespec"]["vertical"] == "cafe"

def test_url_preview_reuses_existing_renderer():
    out = generate_url_reference_preview(BASE)
    assert out["decision"] == "ALLOW"
    assert "<!doctype html>" in out["preview_html"].lower()
    assert out["preview_manifest"]["production"] == "LOCKED"
    assert out["human_approval_required"] is True

def test_http_reference_fails_closed():
    bad = dict(BASE)
    bad["reference_url"] = "http://example.com/reference"
    out = compile_url_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "REFERENCE_URL_UNSAFE"

def test_private_reference_ip_fails_closed():
    bad = dict(BASE)
    bad["reference_url"] = "https://127.0.0.1/reference"
    bad["reference_snapshot"] = dict(BASE["reference_snapshot"], source_url="https://127.0.0.1/reference")
    out = compile_url_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "REFERENCE_URL_UNSAFE"

def test_raw_html_snapshot_is_forbidden():
    bad = dict(BASE)
    bad["reference_snapshot"] = dict(BASE["reference_snapshot"], raw_html="<html>copy me</html>")
    out = compile_url_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "REFERENCE_COPY_CONTENT_FORBIDDEN"

def test_source_mismatch_fails_closed():
    bad = dict(BASE)
    bad["reference_snapshot"] = dict(BASE["reference_snapshot"], source_url="https://other.example/reference")
    out = compile_url_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "REFERENCE_SOURCE_MISMATCH"

def test_unknown_section_signal_fails_closed():
    bad = dict(BASE)
    bad["reference_snapshot"] = dict(BASE["reference_snapshot"], section_types=["hero", "crypto_miner"])
    out = compile_url_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "REFERENCE_SECTION_UNSUPPORTED"

def test_unapproved_capture_fails_closed():
    bad = dict(BASE)
    bad["reference_snapshot"] = dict(BASE["reference_snapshot"], capture_mode="UNVERIFIED")
    out = compile_url_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "REFERENCE_CAPTURE_NOT_APPROVED"

def test_url_reference_is_deterministic():
    a = compile_url_reference_to_sitespec(BASE)
    b = compile_url_reference_to_sitespec(BASE)
    assert a["sitespec"] == b["sitespec"]

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"PASS {len(tests)} LD AI Site Intelligence P1 URL tests")
