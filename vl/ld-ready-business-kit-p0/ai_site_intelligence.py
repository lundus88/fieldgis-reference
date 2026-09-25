from __future__ import annotations

from hashlib import sha256
import json
import re
import ipaddress
from typing import Any
from urllib.parse import urlparse

from ready_business_kit import render_preview, validate_onboarding

SUPPORTED_VERTICALS = {"cafe", "homestay", "tutor"}
DEFAULTS = {
    "cafe": {
        "headline": "Nikmati pilihan terbaik kami dengan lebih mudah.",
        "cta_label": "Hubungi melalui WhatsApp",
        "section_key": "items",
    },
    "homestay": {
        "headline": "Tempah penginapan anda dengan mudah.",
        "cta_label": "Semak melalui WhatsApp",
        "section_key": "rooms",
    },
    "tutor": {
        "headline": "Mulakan pembelajaran yang lebih terarah.",
        "cta_label": "Tanya melalui WhatsApp",
        "section_key": "programs",
    },
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _clean_text(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]

def _infer_vertical(prompt: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit if explicit in SUPPORTED_VERTICALS else None
    p = prompt.lower()
    aliases = {
        "cafe": ("cafe", "café", "coffee", "kopi", "restaurant", "restoran", "food", "f&b"),
        "homestay": ("homestay", "hotel", "room", "bilik", "penginapan", "chalet"),
        "tutor": ("tutor", "tuition", "kelas", "education", "course", "kursus", "academy"),
    }
    matches = [v for v, words in aliases.items() if any(w in p for w in words)]
    return matches[0] if len(matches) == 1 else None

def _safe_http_url(value: Any) -> str | None:
    text = _clean_text(value, 500)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text

def _validate_cards(cards: Any, max_items: int = 50) -> bool:
    if not isinstance(cards, list) or not cards or len(cards) > max_items:
        return False
    return all(isinstance(item, dict) for item in cards)

def compile_prompt_to_sitespec(request: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic P0 contract for Prompt -> SiteSpec.

    This layer intentionally does not call an external model yet. It converts a
    bounded natural-language request plus explicit business facts into a
    machine-readable SiteSpec, failing closed when required facts are absent.
    """
    prompt = _clean_text(request.get("prompt"), 2000)
    if not prompt:
        return {"decision": "HOLD", "reason": "PROMPT_REQUIRED"}

    business_name = _clean_text(request.get("business_name"), 120)
    whatsapp = _clean_text(request.get("whatsapp"), 40)
    if not business_name or not whatsapp:
        return {
            "decision": "HOLD",
            "reason": "BUSINESS_FACTS_REQUIRED",
            "missing": [k for k, v in (("business_name", business_name), ("whatsapp", whatsapp)) if not v],
        }

    vertical = _infer_vertical(prompt, _clean_text(request.get("vertical"), 40) or None)
    if vertical is None:
        return {"decision": "HOLD", "reason": "VERTICAL_UNRESOLVED"}
    if vertical not in SUPPORTED_VERTICALS:
        return {"decision": "HOLD", "reason": "UNSUPPORTED_VERTICAL"}

    cfg = DEFAULTS[vertical]
    section_key = cfg["section_key"]
    cards = request.get(section_key)
    if not _validate_cards(cards):
        return {"decision": "HOLD", "reason": "VERTICAL_CONTENT_INVALID", "missing": [section_key]}

    headline = _clean_text(request.get("headline"), 180) or cfg["headline"]
    cta_label = _clean_text(request.get("cta_label"), 80) or cfg["cta_label"]

    onboarding = {
        "business_name": business_name,
        "vertical": vertical,
        "whatsapp": whatsapp,
        "headline": headline,
        "cta_label": cta_label,
        section_key: cards,
    }
    address = _clean_text(request.get("address"), 500)
    if address:
        onboarding["address"] = address

    for optional in ("maps_url", "social_url"):
        raw = request.get(optional)
        if raw:
            value = _safe_http_url(raw)
            if value is None:
                return {"decision": "HOLD", "reason": "UNSAFE_URL", "field": optional}
            onboarding[optional] = value

    sections = [
        {"type": "hero", "required": True},
        {"type": "vertical_cards", "source": section_key, "required": True},
        {"type": "contact", "required": True},
    ]
    spec = {
        "schema": "ld.ai-site-spec/1",
        "source_mode": "PROMPT",
        "vertical": vertical,
        "business_name": business_name,
        "language": _clean_text(request.get("language"), 20) or "ms",
        "tone": _clean_text(request.get("tone"), 80) or "professional",
        "sections": sections,
        "prompt_digest": _digest({"prompt": prompt}),
        "facts_digest": _digest(onboarding),
        "content_policy": {
            "invent_business_facts": False,
            "copy_third_party_content": False,
            "production_claim": False,
        },
        "authority": {
            "customer_commitment": "HUMAN_ONLY",
            "production_publish": "HUMAN_ONLY",
        },
    }
    return {"decision": "ALLOW", "sitespec": spec, "onboarding": onboarding}

def generate_prompt_preview(request: dict[str, Any]) -> dict[str, Any]:
    compiled = compile_prompt_to_sitespec(request)
    if compiled["decision"] != "ALLOW":
        return compiled
    preview = render_preview(compiled["onboarding"], compiled["sitespec"].get("design_signals"))
    if preview.get("decision") != "ALLOW":
        return preview
    return {
        "decision": "ALLOW",
        "sitespec": compiled["sitespec"],
        "preview_html": preview["html"],
        "preview_manifest": preview["manifest"],
        "production": "LOCKED",
        "human_approval_required": True,
    }


REFERENCE_SECTION_TYPES = {
    "hero", "services", "features", "menu", "rooms", "programs",
    "gallery", "about", "testimonials", "faq", "contact", "footer",
}
REFERENCE_STYLE_HINTS = {
    "minimal", "editorial", "premium", "corporate", "friendly",
    "bold", "clean", "warm", "modern", "classic",
}
REFERENCE_DENSITIES = {"sparse", "balanced", "dense"}
FORBIDDEN_REFERENCE_SNAPSHOT_KEYS = {
    "raw_html", "html", "body_text", "full_text", "css", "javascript",
    "script", "source_code", "images", "assets",
}

def _safe_reference_url(value: Any) -> dict[str, Any] | None:
    text = _clean_text(value, 2000)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None

    host = parsed.hostname.rstrip(".").lower()
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            return None
    except ValueError:
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local") or "." not in host:
            return None
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            return None

    try:
        port = parsed.port
    except ValueError:
        return None
    if port not in (None, 443):
        return None

    path = parsed.path or "/"
    normalized = f"https://{host}{path}"
    return {
        "url": normalized,
        "host": host,
        "query_stripped": bool(parsed.query),
        "fragment_stripped": bool(parsed.fragment),
    }

def _normalize_reference_snapshot(snapshot: Any, reference_url: str) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {"decision": "HOLD", "reason": "REFERENCE_SNAPSHOT_REQUIRED"}
    if len(snapshot) > 20:
        return {"decision": "HOLD", "reason": "REFERENCE_SNAPSHOT_TOO_LARGE"}

    forbidden = sorted(FORBIDDEN_REFERENCE_SNAPSHOT_KEYS.intersection(snapshot))
    if forbidden:
        return {"decision": "HOLD", "reason": "REFERENCE_COPY_CONTENT_FORBIDDEN", "fields": forbidden}

    if snapshot.get("capture_mode") != "APPROVED_READ_ONLY":
        return {"decision": "HOLD", "reason": "REFERENCE_CAPTURE_NOT_APPROVED"}

    source = _safe_reference_url(snapshot.get("source_url"))
    if source is None or source["url"] != reference_url:
        return {"decision": "HOLD", "reason": "REFERENCE_SOURCE_MISMATCH"}

    section_types = snapshot.get("section_types", [])
    if not isinstance(section_types, list) or len(section_types) > 12:
        return {"decision": "HOLD", "reason": "REFERENCE_SECTIONS_INVALID"}
    normalized_sections = []
    for section in section_types:
        key = _clean_text(section, 40).lower()
        if key not in REFERENCE_SECTION_TYPES:
            return {"decision": "HOLD", "reason": "REFERENCE_SECTION_UNSUPPORTED", "section": key}
        if key not in normalized_sections:
            normalized_sections.append(key)

    style_hints = snapshot.get("style_hints", [])
    if not isinstance(style_hints, list) or len(style_hints) > 8:
        return {"decision": "HOLD", "reason": "REFERENCE_STYLE_INVALID"}
    normalized_styles = []
    for hint in style_hints:
        key = _clean_text(hint, 40).lower()
        if key not in REFERENCE_STYLE_HINTS:
            return {"decision": "HOLD", "reason": "REFERENCE_STYLE_UNSUPPORTED", "style": key}
        if key not in normalized_styles:
            normalized_styles.append(key)

    density = _clean_text(snapshot.get("layout_density"), 20).lower() or "balanced"
    if density not in REFERENCE_DENSITIES:
        return {"decision": "HOLD", "reason": "REFERENCE_DENSITY_INVALID"}

    signals = {
        "section_types": normalized_sections,
        "style_hints": normalized_styles,
        "layout_density": density,
        "sticky_navigation": bool(snapshot.get("sticky_navigation", False)),
        "floating_cta": bool(snapshot.get("floating_cta", False)),
    }
    return {"decision": "ALLOW", "signals": signals, "snapshot_digest": _digest(signals)}

def compile_url_reference_to_sitespec(request: dict[str, Any]) -> dict[str, Any]:
    """
    P1 URL-reference contract.

    The URL is a structural design reference only. This function performs no
    network request and never copies third-party body text, HTML, CSS, scripts,
    images or assets. An approved read-only capture adapter must provide the
    bounded structural snapshot.
    """
    reference = _safe_reference_url(request.get("reference_url"))
    if reference is None:
        return {"decision": "HOLD", "reason": "REFERENCE_URL_UNSAFE"}

    snapshot = _normalize_reference_snapshot(request.get("reference_snapshot"), reference["url"])
    if snapshot["decision"] != "ALLOW":
        return snapshot

    base_request = dict(request)
    if not _clean_text(base_request.get("prompt"), 2000):
        vertical = _clean_text(base_request.get("vertical"), 40)
        if vertical not in SUPPORTED_VERTICALS:
            return {"decision": "HOLD", "reason": "VERTICAL_REQUIRED_FOR_URL_MODE"}
        base_request["prompt"] = (
            f"Create an original {vertical} business website using only the "
            "approved structural design signals from the reference."
        )

    base = compile_prompt_to_sitespec(base_request)
    if base["decision"] != "ALLOW":
        return base

    spec = json.loads(json.dumps(base["sitespec"]))
    spec["source_mode"] = "URL_REFERENCE"
    spec["reference"] = {
        "url": reference["url"],
        "host": reference["host"],
        "snapshot_digest": snapshot["snapshot_digest"],
        "structure_only": True,
        "copy_text": False,
        "copy_code": False,
        "copy_assets": False,
        "query_stripped": reference["query_stripped"],
        "fragment_stripped": reference["fragment_stripped"],
    }
    spec["design_signals"] = snapshot["signals"]
    spec["content_policy"]["reference_content_reuse"] = False
    spec["content_policy"]["original_output_required"] = True

    return {
        "decision": "ALLOW",
        "sitespec": spec,
        "onboarding": base["onboarding"],
    }

def generate_url_reference_preview(request: dict[str, Any]) -> dict[str, Any]:
    compiled = compile_url_reference_to_sitespec(request)
    if compiled["decision"] != "ALLOW":
        return compiled
    preview = render_preview(compiled["onboarding"])
    if preview.get("decision") != "ALLOW":
        return preview
    return {
        "decision": "ALLOW",
        "sitespec": compiled["sitespec"],
        "preview_html": preview["html"],
        "preview_manifest": preview["manifest"],
        "production": "LOCKED",
        "human_approval_required": True,
    }


IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
IMAGE_SOURCE_AUTHORITIES = {
    "CUSTOMER_PROVIDED",
    "CUSTOMER_AUTHORIZED",
    "REFERENCE_ONLY",
}
IMAGE_MAX_BYTES = 12 * 1024 * 1024
IMAGE_MAX_DIMENSION = 12000
IMAGE_MAX_PIXELS = 50_000_000
IMAGE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_IMAGE_SNAPSHOT_KEYS = {
    "raw_bytes", "bytes", "base64", "data_url", "raw_image", "image_data",
    "ocr_text", "full_text", "body_text", "extracted_text",
    "embedded_assets", "copied_assets", "source_code",
}

def _normalize_image_evidence(evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        return {"decision": "HOLD", "reason": "IMAGE_EVIDENCE_REQUIRED"}
    if len(evidence) > 24:
        return {"decision": "HOLD", "reason": "IMAGE_EVIDENCE_TOO_LARGE"}

    forbidden = sorted(FORBIDDEN_IMAGE_SNAPSHOT_KEYS.intersection(evidence))
    if forbidden:
        return {"decision": "HOLD", "reason": "IMAGE_COPY_CONTENT_FORBIDDEN", "fields": forbidden}

    if evidence.get("analysis_mode") != "APPROVED_READ_ONLY":
        return {"decision": "HOLD", "reason": "IMAGE_ANALYSIS_NOT_APPROVED"}

    asset_sha256 = _clean_text(evidence.get("asset_sha256"), 80).lower()
    if not IMAGE_SHA256_RE.fullmatch(asset_sha256):
        return {"decision": "HOLD", "reason": "IMAGE_DIGEST_INVALID"}

    mime_type = _clean_text(evidence.get("mime_type"), 40).lower()
    if mime_type not in IMAGE_MIME_TYPES:
        return {"decision": "HOLD", "reason": "IMAGE_MIME_UNSUPPORTED"}

    try:
        width = int(evidence.get("width"))
        height = int(evidence.get("height"))
        byte_size = int(evidence.get("byte_size"))
    except (TypeError, ValueError):
        return {"decision": "HOLD", "reason": "IMAGE_METADATA_INVALID"}

    if width <= 0 or height <= 0 or byte_size <= 0:
        return {"decision": "HOLD", "reason": "IMAGE_METADATA_INVALID"}
    if width > IMAGE_MAX_DIMENSION or height > IMAGE_MAX_DIMENSION:
        return {"decision": "HOLD", "reason": "IMAGE_DIMENSIONS_EXCEEDED"}
    if width * height > IMAGE_MAX_PIXELS:
        return {"decision": "HOLD", "reason": "IMAGE_PIXELS_EXCEEDED"}
    if byte_size > IMAGE_MAX_BYTES:
        return {"decision": "HOLD", "reason": "IMAGE_SIZE_EXCEEDED"}

    source_authority = _clean_text(evidence.get("source_authority"), 40).upper()
    if source_authority not in IMAGE_SOURCE_AUTHORITIES:
        return {"decision": "HOLD", "reason": "IMAGE_SOURCE_AUTHORITY_REQUIRED"}

    section_types = evidence.get("section_types", [])
    if not isinstance(section_types, list) or len(section_types) > 12:
        return {"decision": "HOLD", "reason": "IMAGE_SECTIONS_INVALID"}
    normalized_sections = []
    for section in section_types:
        key = _clean_text(section, 40).lower()
        if key not in REFERENCE_SECTION_TYPES:
            return {"decision": "HOLD", "reason": "IMAGE_SECTION_UNSUPPORTED", "section": key}
        if key not in normalized_sections:
            normalized_sections.append(key)

    style_hints = evidence.get("style_hints", [])
    if not isinstance(style_hints, list) or len(style_hints) > 8:
        return {"decision": "HOLD", "reason": "IMAGE_STYLE_INVALID"}
    normalized_styles = []
    for hint in style_hints:
        key = _clean_text(hint, 40).lower()
        if key not in REFERENCE_STYLE_HINTS:
            return {"decision": "HOLD", "reason": "IMAGE_STYLE_UNSUPPORTED", "style": key}
        if key not in normalized_styles:
            normalized_styles.append(key)

    density = _clean_text(evidence.get("layout_density"), 20).lower() or "balanced"
    if density not in REFERENCE_DENSITIES:
        return {"decision": "HOLD", "reason": "IMAGE_DENSITY_INVALID"}

    signals = {
        "section_types": normalized_sections,
        "style_hints": normalized_styles,
        "layout_density": density,
        "sticky_navigation": bool(evidence.get("sticky_navigation", False)),
        "floating_cta": bool(evidence.get("floating_cta", False)),
    }
    normalized = {
        "asset_sha256": asset_sha256,
        "mime_type": mime_type,
        "width": width,
        "height": height,
        "byte_size": byte_size,
        "source_authority": source_authority,
        "signals": signals,
    }
    return {
        "decision": "ALLOW",
        "evidence": normalized,
        "snapshot_digest": _digest(normalized),
    }

def compile_image_reference_to_sitespec(request: dict[str, Any]) -> dict[str, Any]:
    """
    P2 Image/Screenshot-reference contract.

    The image contributes only bounded structural design signals. This function
    does not decode image bytes, perform OCR, copy text/assets or invoke a vision
    model. A separately approved read-only visual-analysis adapter must produce
    the bounded evidence manifest.
    """
    image = _normalize_image_evidence(request.get("image_evidence"))
    if image["decision"] != "ALLOW":
        return image

    base_request = dict(request)
    if not _clean_text(base_request.get("prompt"), 2000):
        vertical = _clean_text(base_request.get("vertical"), 40)
        if vertical not in SUPPORTED_VERTICALS:
            return {"decision": "HOLD", "reason": "VERTICAL_REQUIRED_FOR_IMAGE_MODE"}
        base_request["prompt"] = (
            f"Create an original {vertical} business website using only the "
            "approved structural design signals from the supplied image."
        )

    base = compile_prompt_to_sitespec(base_request)
    if base["decision"] != "ALLOW":
        return base

    evidence = image["evidence"]
    spec = json.loads(json.dumps(base["sitespec"]))
    spec["source_mode"] = "IMAGE_REFERENCE"
    spec["image_reference"] = {
        "asset_sha256": evidence["asset_sha256"],
        "mime_type": evidence["mime_type"],
        "width": evidence["width"],
        "height": evidence["height"],
        "byte_size": evidence["byte_size"],
        "source_authority": evidence["source_authority"],
        "snapshot_digest": image["snapshot_digest"],
        "structure_only": True,
        "ocr_text_reuse": False,
        "copy_assets": False,
        "copy_branding": False,
    }
    spec["design_signals"] = evidence["signals"]
    spec["content_policy"]["reference_content_reuse"] = False
    spec["content_policy"]["original_output_required"] = True
    spec["content_policy"]["ocr_copy_forbidden"] = True

    return {
        "decision": "ALLOW",
        "sitespec": spec,
        "onboarding": base["onboarding"],
    }

def generate_image_reference_preview(request: dict[str, Any]) -> dict[str, Any]:
    compiled = compile_image_reference_to_sitespec(request)
    if compiled["decision"] != "ALLOW":
        return compiled
    preview = render_preview(compiled["onboarding"])
    if preview.get("decision") != "ALLOW":
        return preview
    return {
        "decision": "ALLOW",
        "sitespec": compiled["sitespec"],
        "preview_html": preview["html"],
        "preview_manifest": preview["manifest"],
        "production": "LOCKED",
        "human_approval_required": True,
    }


EDIT_TONES = {
    "professional", "premium", "friendly", "warm", "modern",
    "minimal", "corporate", "bold", "classic",
}
EDIT_HEADLINE_SCALES = {"compact", "standard", "large"}
EDIT_MAX_ACTIONS = 8
EDIT_ALLOWED_OPS = {
    "SET_HEADLINE",
    "SET_CTA_LABEL",
    "SET_TONE",
    "SET_STYLE_HINTS",
    "SET_LAYOUT_DENSITY",
    "SET_HEADLINE_SCALE",
    "REORDER_CARDS",
}

def create_edit_state(
    sitespec: dict[str, Any],
    onboarding: dict[str, Any],
    revision: int = 0,
) -> dict[str, Any]:
    if not isinstance(sitespec, dict) or sitespec.get("schema") != "ld.ai-site-spec/1":
        return {"decision": "HOLD", "reason": "EDIT_SITESPEC_INVALID"}
    if not isinstance(onboarding, dict):
        return {"decision": "HOLD", "reason": "EDIT_ONBOARDING_INVALID"}

    validated = validate_onboarding(onboarding)
    if validated.get("decision") != "ALLOW":
        return {"decision": "HOLD", "reason": "EDIT_ONBOARDING_INVALID"}

    authority = sitespec.get("authority", {})
    if (
        authority.get("customer_commitment") != "HUMAN_ONLY"
        or authority.get("production_publish") != "HUMAN_ONLY"
    ):
        return {"decision": "HOLD", "reason": "EDIT_AUTHORITY_INVARIANT"}

    if sitespec.get("vertical") != onboarding.get("vertical"):
        return {"decision": "HOLD", "reason": "EDIT_VERTICAL_MISMATCH"}
    if sitespec.get("business_name") != onboarding.get("business_name"):
        return {"decision": "HOLD", "reason": "EDIT_BUSINESS_NAME_MISMATCH"}

    if not isinstance(revision, int) or revision < 0 or revision > 10000:
        return {"decision": "HOLD", "reason": "EDIT_REVISION_INVALID"}

    spec_copy = json.loads(json.dumps(sitespec))
    onboarding_copy = json.loads(json.dumps(onboarding))
    core = {
        "schema": "ld.ai-site-edit-state/1",
        "revision": revision,
        "sitespec": spec_copy,
        "onboarding": onboarding_copy,
    }
    return {
        "decision": "ALLOW",
        **core,
        "state_digest": _digest(core),
    }

def _normalize_edit_action(
    action: Any,
    onboarding: dict[str, Any],
    seen_ops: set[str],
) -> dict[str, Any]:
    if not isinstance(action, dict):
        return {"decision": "HOLD", "reason": "EDIT_ACTION_INVALID"}

    op = _clean_text(action.get("op"), 60).upper()
    if op not in EDIT_ALLOWED_OPS:
        return {"decision": "HOLD", "reason": "EDIT_OPERATION_FORBIDDEN", "op": op}
    if op in seen_ops:
        return {"decision": "HOLD", "reason": "EDIT_DUPLICATE_OPERATION", "op": op}

    allowed_keys = {
        "SET_HEADLINE": {"op", "value"},
        "SET_CTA_LABEL": {"op", "value"},
        "SET_TONE": {"op", "value"},
        "SET_STYLE_HINTS": {"op", "value"},
        "SET_LAYOUT_DENSITY": {"op", "value"},
        "SET_HEADLINE_SCALE": {"op", "value"},
        "REORDER_CARDS": {"op", "order"},
    }[op]
    extra = sorted(set(action) - allowed_keys)
    if extra:
        return {"decision": "HOLD", "reason": "EDIT_ACTION_FIELDS_FORBIDDEN", "fields": extra}

    if op == "SET_HEADLINE":
        value = _clean_text(action.get("value"), 180)
        if not value:
            return {"decision": "HOLD", "reason": "EDIT_HEADLINE_INVALID"}
        normalized = {"op": op, "value": value}

    elif op == "SET_CTA_LABEL":
        value = _clean_text(action.get("value"), 80)
        if not value:
            return {"decision": "HOLD", "reason": "EDIT_CTA_INVALID"}
        normalized = {"op": op, "value": value}

    elif op == "SET_TONE":
        value = _clean_text(action.get("value"), 40).lower()
        if value not in EDIT_TONES:
            return {"decision": "HOLD", "reason": "EDIT_TONE_INVALID"}
        normalized = {"op": op, "value": value}

    elif op == "SET_STYLE_HINTS":
        value = action.get("value")
        if not isinstance(value, list) or len(value) > 4:
            return {"decision": "HOLD", "reason": "EDIT_STYLE_HINTS_INVALID"}
        hints: list[str] = []
        for hint in value:
            key = _clean_text(hint, 40).lower()
            if key not in REFERENCE_STYLE_HINTS:
                return {"decision": "HOLD", "reason": "EDIT_STYLE_HINT_INVALID", "style": key}
            if key not in hints:
                hints.append(key)
        normalized = {"op": op, "value": hints}

    elif op == "SET_LAYOUT_DENSITY":
        value = _clean_text(action.get("value"), 20).lower()
        if value not in REFERENCE_DENSITIES:
            return {"decision": "HOLD", "reason": "EDIT_LAYOUT_DENSITY_INVALID"}
        normalized = {"op": op, "value": value}

    elif op == "SET_HEADLINE_SCALE":
        value = _clean_text(action.get("value"), 20).lower()
        if value not in EDIT_HEADLINE_SCALES:
            return {"decision": "HOLD", "reason": "EDIT_HEADLINE_SCALE_INVALID"}
        normalized = {"op": op, "value": value}

    else:
        section_key = DEFAULTS[onboarding["vertical"]]["section_key"]
        cards = onboarding.get(section_key, [])
        order = action.get("order")
        if (
            not isinstance(order, list)
            or len(order) != len(cards)
            or not all(isinstance(i, int) for i in order)
            or sorted(order) != list(range(len(cards)))
        ):
            return {"decision": "HOLD", "reason": "EDIT_CARD_ORDER_INVALID"}
        normalized = {"op": op, "order": order}

    return {"decision": "ALLOW", "action": normalized}

def compile_conversational_edit(
    state: dict[str, Any],
    edit: dict[str, Any],
) -> dict[str, Any]:
    """
    P3 conversational-edit contract.

    Free-form conversation text is evidence of user intent only. A model or UI
    may propose bounded edit actions, but only this allowlisted action language
    may mutate SiteSpec/onboarding state.
    """
    if not isinstance(state, dict) or state.get("schema") != "ld.ai-site-edit-state/1":
        return {"decision": "HOLD", "reason": "EDIT_STATE_REQUIRED"}
    if not isinstance(edit, dict):
        return {"decision": "HOLD", "reason": "EDIT_REQUEST_INVALID"}

    rebuilt = create_edit_state(
        state.get("sitespec"),
        state.get("onboarding"),
        state.get("revision"),
    )
    if rebuilt.get("decision") != "ALLOW":
        return rebuilt
    if rebuilt["state_digest"] != state.get("state_digest"):
        return {"decision": "HOLD", "reason": "EDIT_STATE_TAMPERED"}

    if edit.get("base_state_digest") != state["state_digest"]:
        return {"decision": "HOLD", "reason": "EDIT_STALE_BASE"}

    request_text = _clean_text(edit.get("edit_request"), 2000)
    if not request_text:
        return {"decision": "HOLD", "reason": "EDIT_REQUEST_TEXT_REQUIRED"}

    actions = edit.get("actions")
    if (
        not isinstance(actions, list)
        or not actions
        or len(actions) > EDIT_MAX_ACTIONS
    ):
        return {"decision": "HOLD", "reason": "EDIT_ACTIONS_INVALID"}

    normalized_actions: list[dict[str, Any]] = []
    seen_ops: set[str] = set()
    for action in actions:
        normalized = _normalize_edit_action(action, state["onboarding"], seen_ops)
        if normalized.get("decision") != "ALLOW":
            return normalized
        op = normalized["action"]["op"]
        seen_ops.add(op)
        normalized_actions.append(normalized["action"])

    spec = json.loads(json.dumps(state["sitespec"]))
    onboarding = json.loads(json.dumps(state["onboarding"]))
    design = json.loads(json.dumps(spec.get("design_signals", {})))
    changed_fields: list[str] = []

    for action in normalized_actions:
        op = action["op"]
        if op == "SET_HEADLINE":
            onboarding["headline"] = action["value"]
            changed_fields.append("headline")
        elif op == "SET_CTA_LABEL":
            onboarding["cta_label"] = action["value"]
            changed_fields.append("cta_label")
        elif op == "SET_TONE":
            spec["tone"] = action["value"]
            changed_fields.append("tone")
        elif op == "SET_STYLE_HINTS":
            design["style_hints"] = action["value"]
            changed_fields.append("design_signals.style_hints")
        elif op == "SET_LAYOUT_DENSITY":
            design["layout_density"] = action["value"]
            changed_fields.append("design_signals.layout_density")
        elif op == "SET_HEADLINE_SCALE":
            design["headline_scale"] = action["value"]
            changed_fields.append("design_signals.headline_scale")
        elif op == "REORDER_CARDS":
            section_key = DEFAULTS[onboarding["vertical"]]["section_key"]
            cards = onboarding[section_key]
            onboarding[section_key] = [cards[i] for i in action["order"]]
            changed_fields.append(section_key)

    spec["design_signals"] = design
    spec["facts_digest"] = _digest(onboarding)
    spec.setdefault("content_policy", {})["conversation_business_fact_mutation"] = False
    next_revision = state["revision"] + 1
    spec["revision"] = next_revision
    spec["last_edit"] = {
        "schema": "ld.ai-site-edit-evidence/1",
        "base_state_digest": state["state_digest"],
        "edit_request_digest": _digest({"edit_request": request_text}),
        "actions_digest": _digest(normalized_actions),
        "changed_fields": changed_fields,
        "revision": next_revision,
    }

    new_state = create_edit_state(spec, onboarding, next_revision)
    if new_state.get("decision") != "ALLOW":
        return new_state

    return {
        "decision": "ALLOW",
        "state": {
            "schema": new_state["schema"],
            "revision": new_state["revision"],
            "sitespec": new_state["sitespec"],
            "onboarding": new_state["onboarding"],
            "state_digest": new_state["state_digest"],
        },
        "normalized_actions": normalized_actions,
        "changed_fields": changed_fields,
    }

def generate_conversational_edit_preview(
    state: dict[str, Any],
    edit: dict[str, Any],
) -> dict[str, Any]:
    compiled = compile_conversational_edit(state, edit)
    if compiled.get("decision") != "ALLOW":
        return compiled

    new_state = compiled["state"]
    preview = render_preview(
        new_state["onboarding"],
        new_state["sitespec"].get("design_signals"),
    )
    if preview.get("decision") != "ALLOW":
        return preview

    return {
        "decision": "ALLOW",
        "state": new_state,
        "normalized_actions": compiled["normalized_actions"],
        "changed_fields": compiled["changed_fields"],
        "preview_html": preview["html"],
        "preview_manifest": preview["manifest"],
        "production": "LOCKED",
        "human_approval_required": True,
    }
