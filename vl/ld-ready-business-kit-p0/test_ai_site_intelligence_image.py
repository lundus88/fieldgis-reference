from ai_site_intelligence import compile_image_reference_to_sitespec, generate_image_reference_preview

BASE = {
    "image_evidence": {
        "analysis_mode": "APPROVED_READ_ONLY",
        "asset_sha256": "a" * 64,
        "mime_type": "image/png",
        "width": 1440,
        "height": 900,
        "byte_size": 450000,
        "source_authority": "CUSTOMER_PROVIDED",
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

def test_image_reference_compiles_to_sitespec():
    out = compile_image_reference_to_sitespec(BASE)
    assert out["decision"] == "ALLOW"
    spec = out["sitespec"]
    assert spec["source_mode"] == "IMAGE_REFERENCE"
    assert spec["image_reference"]["asset_sha256"] == "a" * 64
    assert spec["image_reference"]["structure_only"] is True
    assert spec["image_reference"]["ocr_text_reuse"] is False
    assert spec["content_policy"]["original_output_required"] is True
    assert spec["design_signals"]["section_types"] == ["hero", "services", "testimonials", "contact"]

def test_image_preview_reuses_existing_renderer():
    out = generate_image_reference_preview(BASE)
    assert out["decision"] == "ALLOW"
    assert "<!doctype html>" in out["preview_html"].lower()
    assert out["preview_manifest"]["production"] == "LOCKED"
    assert out["human_approval_required"] is True

def test_invalid_digest_fails_closed():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], asset_sha256="abc")
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_DIGEST_INVALID"

def test_unsupported_mime_fails_closed():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], mime_type="image/svg+xml")
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_MIME_UNSUPPORTED"

def test_oversize_image_fails_closed():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], byte_size=20 * 1024 * 1024)
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_SIZE_EXCEEDED"

def test_excessive_pixels_fail_closed():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], width=10000, height=6000)
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_PIXELS_EXCEEDED"

def test_raw_or_ocr_content_is_forbidden():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], ocr_text="copy this text")
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_COPY_CONTENT_FORBIDDEN"

def test_source_authority_required():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], source_authority="UNKNOWN")
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_SOURCE_AUTHORITY_REQUIRED"

def test_unapproved_analysis_fails_closed():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], analysis_mode="UNVERIFIED")
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_ANALYSIS_NOT_APPROVED"

def test_unknown_section_signal_fails_closed():
    bad = dict(BASE)
    bad["image_evidence"] = dict(BASE["image_evidence"], section_types=["hero", "malware"])
    out = compile_image_reference_to_sitespec(bad)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "IMAGE_SECTION_UNSUPPORTED"

def test_image_reference_is_deterministic():
    a = compile_image_reference_to_sitespec(BASE)
    b = compile_image_reference_to_sitespec(BASE)
    assert a["sitespec"] == b["sitespec"]

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"PASS {len(tests)} LD AI Site Intelligence P2 image tests")
