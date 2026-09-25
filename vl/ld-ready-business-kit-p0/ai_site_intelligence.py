from __future__ import annotations

from hashlib import sha256
import json
import re
import ipaddress
from typing import Any
from urllib.parse import urlparse

from ready_business_kit import render_preview

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
