from ai_site_intelligence import (
    compile_prompt_to_sitespec,
    create_edit_state,
    compile_conversational_edit,
    generate_conversational_edit_preview,
)

BASE_REQUEST = {
    "prompt": "Bina website premium untuk cafe tempatan.",
    "business_name": "Kopi Contoh",
    "whatsapp": "60123456789",
    "headline": "Kopi yang sedap setiap hari.",
    "cta_label": "Order sekarang",
    "items": [
        {"name": "Latte", "price": "RM8", "description": "Kopi susu."},
        {"name": "Nasi Lemak", "price": "RM10", "description": "Sarapan."},
        {"name": "Set Lunch", "price": "RM15", "description": "Makan tengah hari."},
    ],
}

def make_state():
    compiled = compile_prompt_to_sitespec(BASE_REQUEST)
    assert compiled["decision"] == "ALLOW"
    state = create_edit_state(compiled["sitespec"], compiled["onboarding"])
    assert state["decision"] == "ALLOW"
    return {
        "schema": state["schema"],
        "revision": state["revision"],
        "sitespec": state["sitespec"],
        "onboarding": state["onboarding"],
        "state_digest": state["state_digest"],
    }

def make_edit(state):
    return {
        "base_state_digest": state["state_digest"],
        "edit_request": "Besarkan tajuk, jadikan lebih premium dan susun Set Lunch di depan.",
        "actions": [
            {"op": "SET_HEADLINE", "value": "Kopi Premium, Lebih Mudah Dinikmati."},
            {"op": "SET_CTA_LABEL", "value": "Tempah melalui WhatsApp"},
            {"op": "SET_TONE", "value": "premium"},
            {"op": "SET_STYLE_HINTS", "value": ["premium", "clean"]},
            {"op": "SET_LAYOUT_DENSITY", "value": "sparse"},
            {"op": "SET_HEADLINE_SCALE", "value": "large"},
            {"op": "REORDER_CARDS", "order": [2, 0, 1]},
        ],
    }

def test_create_edit_state_is_deterministic():
    a = make_state()
    b = make_state()
    assert a["state_digest"] == b["state_digest"]
    assert a["revision"] == 0

def test_conversational_edit_applies_bounded_actions():
    state = make_state()
    out = compile_conversational_edit(state, make_edit(state))
    assert out["decision"] == "ALLOW"
    new_state = out["state"]
    assert new_state["revision"] == 1
    assert new_state["onboarding"]["headline"] == "Kopi Premium, Lebih Mudah Dinikmati."
    assert new_state["onboarding"]["cta_label"] == "Tempah melalui WhatsApp"
    assert new_state["sitespec"]["tone"] == "premium"
    assert new_state["sitespec"]["design_signals"]["style_hints"] == ["premium", "clean"]
    assert new_state["sitespec"]["design_signals"]["layout_density"] == "sparse"
    assert new_state["sitespec"]["design_signals"]["headline_scale"] == "large"
    assert new_state["onboarding"]["items"][0]["name"] == "Set Lunch"
    assert new_state["onboarding"]["business_name"] == BASE_REQUEST["business_name"]
    assert new_state["onboarding"]["whatsapp"] == BASE_REQUEST["whatsapp"]
    assert new_state["sitespec"]["authority"]["production_publish"] == "HUMAN_ONLY"
    assert new_state["sitespec"]["authority"]["customer_commitment"] == "HUMAN_ONLY"

def test_preview_reflects_conversational_edit_and_existing_renderer():
    state = make_state()
    out = generate_conversational_edit_preview(state, make_edit(state))
    assert out["decision"] == "ALLOW"
    html = out["preview_html"]
    assert "Kopi Premium, Lebih Mudah Dinikmati." in html
    assert "Tempah melalui WhatsApp" in html
    assert "clamp(44px,9vw,92px)" in html
    assert "padding:32px" in html
    assert "border-radius:20px" in html
    assert html.index("Set Lunch") < html.index("Latte") < html.index("Nasi Lemak")
    manifest = out["preview_manifest"]
    assert manifest["design_signals"]["layout_density"] == "sparse"
    assert manifest["design_signals"]["headline_scale"] == "large"
    assert manifest["production"] == "LOCKED"
    assert out["human_approval_required"] is True

def test_stale_base_fails_closed():
    state = make_state()
    edit = make_edit(state)
    edit["base_state_digest"] = "0" * 64
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_STALE_BASE"

def test_tampered_state_fails_closed():
    state = make_state()
    state["onboarding"]["headline"] = "Tampered"
    out = compile_conversational_edit(state, make_edit(state))
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_STATE_TAMPERED"

def test_forbidden_business_fact_operation_fails_closed():
    state = make_state()
    edit = {
        "base_state_digest": state["state_digest"],
        "edit_request": "Tukar nombor WhatsApp.",
        "actions": [{"op": "SET_WHATSAPP", "value": "60999999999"}],
    }
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_OPERATION_FORBIDDEN"

def test_duplicate_operation_fails_closed():
    state = make_state()
    edit = {
        "base_state_digest": state["state_digest"],
        "edit_request": "Cuba dua tajuk.",
        "actions": [
            {"op": "SET_HEADLINE", "value": "Tajuk A"},
            {"op": "SET_HEADLINE", "value": "Tajuk B"},
        ],
    }
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_DUPLICATE_OPERATION"

def test_extra_action_fields_fail_closed():
    state = make_state()
    edit = {
        "base_state_digest": state["state_digest"],
        "edit_request": "Tukar tajuk.",
        "actions": [{"op": "SET_HEADLINE", "value": "Tajuk Baru", "html": "<script/>"}],
    }
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_ACTION_FIELDS_FORBIDDEN"

def test_invalid_card_order_fails_closed():
    state = make_state()
    edit = {
        "base_state_digest": state["state_digest"],
        "edit_request": "Susun kad.",
        "actions": [{"op": "REORDER_CARDS", "order": [0, 0, 1]}],
    }
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_CARD_ORDER_INVALID"

def test_boolean_card_indexes_fail_closed():
    state = make_state()
    edit = {
        "base_state_digest": state["state_digest"],
        "edit_request": "Susun kad.",
        "actions": [{"op": "REORDER_CARDS", "order": [True, 1, 2]}],
    }
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_CARD_ORDER_INVALID"

def test_overlong_headline_fails_closed():
    state = make_state()
    edit = {
        "base_state_digest": state["state_digest"],
        "edit_request": "Tukar tajuk.",
        "actions": [{"op": "SET_HEADLINE", "value": "x" * 181}],
    }
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_HEADLINE_INVALID"

def test_overlong_edit_request_fails_closed():
    state = make_state()
    edit = {
        "base_state_digest": state["state_digest"],
        "edit_request": "x" * 2001,
        "actions": [{"op": "SET_TONE", "value": "premium"}],
    }
    out = compile_conversational_edit(state, edit)
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_REQUEST_TEXT_TOO_LONG"

def test_authority_tampering_blocks_edit_state():
    compiled = compile_prompt_to_sitespec(BASE_REQUEST)
    compiled["sitespec"]["authority"]["production_publish"] = "AUTO"
    out = create_edit_state(compiled["sitespec"], compiled["onboarding"])
    assert out["decision"] == "HOLD"
    assert out["reason"] == "EDIT_AUTHORITY_INVARIANT"

def test_second_turn_uses_new_digest_and_revision():
    state = make_state()
    first = compile_conversational_edit(state, make_edit(state))
    assert first["decision"] == "ALLOW"
    next_state = first["state"]
    second_edit = {
        "base_state_digest": next_state["state_digest"],
        "edit_request": "Jadikan susun atur lebih padat.",
        "actions": [{"op": "SET_LAYOUT_DENSITY", "value": "dense"}],
    }
    second = compile_conversational_edit(next_state, second_edit)
    assert second["decision"] == "ALLOW"
    assert second["state"]["revision"] == 2
    assert second["state"]["sitespec"]["design_signals"]["layout_density"] == "dense"
    assert second["state"]["state_digest"] != next_state["state_digest"]

def test_same_state_and_edit_are_deterministic():
    state = make_state()
    edit = make_edit(state)
    a = compile_conversational_edit(state, edit)
    b = compile_conversational_edit(state, edit)
    assert a["state"]["state_digest"] == b["state"]["state_digest"]
    assert a["normalized_actions"] == b["normalized_actions"]

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"PASS {len(tests)} LD AI Site Intelligence P3 conversational edit tests")
